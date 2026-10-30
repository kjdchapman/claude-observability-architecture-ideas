#!/usr/bin/env python3
"""Validate an Open Knowledge Format (OKF v0.2) vault.

Reports on frontmatter, link integrity, reserved files, connectivity (unreferenced
and unreachable concept notes), hub nodes (concept-degree outliers and how much
connectivity depends on each), and v0.2 trust/provenance/lifecycle signals for a
vault directory. Standard library only.

"unreferenced" counts inbound links from concept notes only — index/log links are
navigation, not knowledge, so being listed in an index does not count as a
reference. "unreachable" traverses index links (that is what indexes are for).

Exit codes:
  0  no hard failures (link/connectivity/lint issues are warnings only)
  1  hard failure: a non-reserved .md is missing a non-empty `type` or
     `description`, or has a malformed frontmatter block
  2  usage error (bad path)

OKF tolerates broken links by design, so links never gate CI. `description` does:
it is the one-line recall aid an agent uses to judge relevance, and it is what the
vault map (okf_map.py) shows a model when it decides what to read — a note without
one is effectively invisible to any agent consuming the vault.

v0.2 notes: `generated.at` supersedes the v0.1 `timestamp` (either satisfies the
recency check); `resource` may be a URL or a path; `sources` frontmatter supersedes
a body `# Citations` list. All v0.2 signal issues are warnings, never hard failures.

Usage:
  python3 validate_okf.py <vault-dir> [--quiet] [--strict-links]
    --quiet         print only the summary counts
    --strict-links  also exit non-zero when internal links are broken
"""

import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_graph import (  # noqa: E402
    ACTOR, DATE, ISO_TS, MD_LINK, RESERVED, STATUSES,
    clean_target, collect_md_files, is_internal, parse_frontmatter, resolve,
    today, trust_tier,
)


def build_report(vault, quiet=False, strict_links=False):
    """Analyse a vault and return (report_text, exit_code).

    Split out of main() so the MCP server can serve the identical report without
    shelling out to this script — a client reaching a vault over MCP has no way to
    locate a file on the host, and CLAUDE_PLUGIN_ROOT is not exported to shell
    commands either.

    Raises ValueError when `vault` is not a directory or holds no Markdown.
    """
    if not os.path.isdir(vault):
        raise ValueError(f"not a directory: {vault}")
    files = collect_md_files(vault)
    if not files:
        raise ValueError(f"no .md files found under {vault}")

    now = today()
    hard_failures = []      # missing/empty type or description; bad frontmatter
    fm_warnings = []        # missing title/description/recency
    lint_warnings = []      # v0.2 signal + format lints
    broken_links = []       # (source, target)
    stale_files = []        # stale_after reached (advisory)
    concept_files = set()
    reachable = set()
    index_files = []
    link_graph = {}
    tiers = {"unverified": 0, "machine-confirmed": 0, "human-reviewed": 0}
    root_okf_version = None

    for path in files:
        rel = os.path.relpath(path, vault)
        base = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            fm_warnings.append(f"{rel}: unreadable ({e})")
            continue

        # --- links (all files, including reserved) ---
        targets = set()
        for m in MD_LINK.finditer(text):
            target = clean_target(m.group(1))
            if not is_internal(target):
                continue
            resolved = resolve(target, path, vault)
            if os.path.exists(resolved):
                targets.add(resolved)
            elif os.path.exists(resolved + ".md"):
                targets.add(resolved + ".md")
            else:
                broken_links.append((rel, target))
        link_graph[path] = targets

        if base == "index.md":
            index_files.append(path)
            if os.path.dirname(path) == vault:  # bundle-root version declaration
                fm_root, _ = parse_frontmatter(text)
                root_okf_version = fm_root.get("okf_version")

        # --- frontmatter (concept notes only) ---
        if base in RESERVED:
            continue
        concept_files.add(path)
        fm, closed = parse_frontmatter(text)
        if not closed:
            hard_failures.append(f"{rel}: no closed YAML frontmatter block")
            continue
        if not fm.get("type"):
            hard_failures.append(f"{rel}: missing or empty `type`")
        # `description` is a hard failure, not a warning: it is the only signal a
        # consuming agent has for judging a note's relevance from a map or search
        # result, so a note without one cannot be found by the tools that matter.
        if not fm.get("description"):
            hard_failures.append(f"{rel}: missing or empty `description`")
        if not fm.get("title"):
            fm_warnings.append(f"{rel}: missing `title`")

        # recency: generated.at (v0.2) or legacy timestamp (v0.1)
        gen = fm.get("generated") if isinstance(fm.get("generated"), dict) else None
        gen_at = gen.get("at") if gen else None
        ts = fm.get("timestamp")
        if not gen_at and not ts:
            fm_warnings.append(f"{rel}: no `generated.at` (or legacy `timestamp`)")
        for label, val in (("generated.at", gen_at), ("timestamp", ts)):
            if val and not ISO_TS.match(val):
                lint_warnings.append(f"{rel}: `{label}` not ISO-8601: {val}")

        # trust: actor convention on generated.by and verified[].by/at
        if gen:
            by = gen.get("by")
            if not by:
                lint_warnings.append(f"{rel}: `generated` present but missing `by`")
            elif not ACTOR.match(by):
                lint_warnings.append(f"{rel}: `generated.by` breaks actor convention: {by}")
        verified = fm.get("verified") or []
        for k, v in enumerate(verified):
            if not v.get("by"):
                lint_warnings.append(f"{rel}: verified[{k}] missing `by`")
            elif not ACTOR.match(v["by"]):
                lint_warnings.append(f"{rel}: verified[{k}].by breaks actor convention: {v['by']}")
            if not v.get("at"):
                lint_warnings.append(f"{rel}: verified[{k}] missing `at`")
            elif not ISO_TS.match(v["at"]):
                lint_warnings.append(f"{rel}: verified[{k}].at not ISO-8601: {v['at']}")
        tiers[trust_tier(verified)] += 1

        # lifecycle
        status = fm.get("status")
        if status and status not in STATUSES:
            lint_warnings.append(f"{rel}: `status` not draft|stable|deprecated: {status}")
        sa = fm.get("stale_after")
        if sa:
            if not DATE.match(sa):
                lint_warnings.append(f"{rel}: `stale_after` not YYYY-MM-DD: {sa}")
            elif sa <= now:
                stale_files.append(f"{rel} (stale_after {sa})")

        # provenance
        for k, s in enumerate(fm.get("sources") or []):
            if not s.get("resource"):
                lint_warnings.append(f"{rel}: sources[{k}] missing `resource`")
            lm = s.get("last_modified")
            if lm and not DATE.match(lm):
                lint_warnings.append(f"{rel}: sources[{k}].last_modified not YYYY-MM-DD: {lm}")

    # --- reachability from every index.md (index edges count — that's discovery) ---
    stack = list(index_files)
    while stack:
        cur = stack.pop()
        for nxt in link_graph.get(cur, ()):
            if nxt not in reachable:
                reachable.add(nxt)
                stack.append(nxt)
    unreachable = sorted(
        os.path.relpath(f, vault) for f in concept_files if f not in reachable
    )

    # --- concept-only connectivity: inbound/outbound among concept notes only.
    # Index/log links are navigation, not knowledge, so they are excluded — being
    # listed in an index must not count as a reference.
    inbound_sources = {f: set() for f in concept_files}
    outbound_targets = {f: set() for f in concept_files}
    for src, tgts in link_graph.items():
        if os.path.basename(src) in RESERVED:
            continue
        for t in tgts:
            if t in inbound_sources and t != src:
                inbound_sources[t].add(src)
                outbound_targets[src].add(t)
    unreferenced = sorted(
        os.path.relpath(f, vault) for f in concept_files if not inbound_sources[f]
    )

    # --- hub detection + removal impact (advisory). A concept-degree outlier may be
    # a legitimate central concept OR an index masquerading as a concept; the
    # removal impact tells them apart by how much connectivity actually depends on
    # it. "remove → +N unreferenced/unreachable" = what the hub is holding together.
    concept_degree = {f: len(inbound_sources[f]) + len(outbound_targets[f])
                      for f in concept_files}
    degrees = sorted(concept_degree.values())
    median_deg = statistics.median(degrees) if degrees else 0
    hub_threshold = max(6, round(3 * median_deg))
    hubs = sorted((f for f in concept_files if concept_degree[f] >= hub_threshold),
                  key=lambda f: -concept_degree[f])
    base_reach = {f for f in concept_files if f in reachable}
    hub_report = []
    for h in hubs:
        newly_unref = sum(1 for c in concept_files
                          if c != h and inbound_sources[c] == {h})
        seen, stack = set(), list(index_files)
        while stack:                       # reachability with h removed
            cur = stack.pop()
            for nxt in link_graph.get(cur, ()):
                if nxt == h or nxt in seen:
                    continue
                seen.add(nxt)
                stack.append(nxt)
        newly_unreach = sum(1 for c in base_reach if c != h and c not in seen)
        hub_report.append((os.path.relpath(h, vault), concept_degree[h],
                           newly_unref, newly_unreach))

    # --- report ---
    out = []

    def section(title, items):
        if quiet or not items:
            return
        out.append(f"\n{title} ({len(items)}):")
        for it in items:
            if isinstance(it, tuple):
                out.append(f"  - {it[0]}  ->  {it[1]}")
            else:
                out.append(f"  - {it}")

    out.append(f"OKF vault report: {vault}")
    out.append(f"  okf_version    : {root_okf_version or 'unset (root index.md)'}")
    out.append(f"  markdown files : {len(files)}")
    out.append(f"  concept notes  : {len(concept_files)}")
    out.append(f"  reserved files : {sum(1 for f in files if os.path.basename(f) in RESERVED)}")
    out.append(f"  hard failures  : {len(hard_failures)}")
    out.append(f"  fm warnings    : {len(fm_warnings)}")
    out.append(f"  lint warnings  : {len(lint_warnings)}")
    out.append(f"  broken links   : {len(broken_links)}")
    out.append(f"  unreferenced   : {len(unreferenced)}")
    out.append(f"  unreachable    : {len(unreachable)}")
    out.append(f"  hubs           : {len(hubs)} (concept-degree \u2265 {hub_threshold}; median {median_deg:g})")
    out.append(f"  stale notes    : {len(stale_files)}")
    out.append(f"  trust tiers    : {tiers['human-reviewed']} human-reviewed, "
               f"{tiers['machine-confirmed']} machine-confirmed, "
               f"{tiers['unverified']} unverified")

    section("HARD FAILURES (missing/empty `type` or `description`)", hard_failures)
    section("Frontmatter warnings", fm_warnings)
    section("Lint warnings (v0.2 signals + formats)", lint_warnings)
    section("Broken internal links", broken_links)
    section("Unreferenced (no inbound link from a concept note)", unreferenced)
    section("Unreachable (no path from any index.md)", unreachable)
    if not quiet and hub_report:
        out.append(f"\nHub nodes ({len(hub_report)}) \u2014 concept-degree outliers. High "
                   f"degree is not itself a fault; check what each holds together:")
        for rel, deg, nu, nr in hub_report:
            tail = (f"remove \u2192 +{nu} unreferenced, +{nr} unreachable"
                    if (nu or nr) else "remove \u2192 no notes orphaned (well-integrated)")
            out.append(f"  - {rel}  degree {deg} \u00b7 {tail}")
    section("Stale (stale_after reached; advisory)", stale_files)

    code = 1 if hard_failures or (strict_links and broken_links) else 0
    return "\n".join(out), code


def main():
    ap = argparse.ArgumentParser(description="Validate an OKF v0.2 vault.")
    ap.add_argument("vault", help="path to the vault directory")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    ap.add_argument("--strict-links", action="store_true",
                    help="exit non-zero on broken internal links too")
    args = ap.parse_args()

    try:
        text, code = build_report(os.path.abspath(args.vault), args.quiet,
                                  args.strict_links)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
