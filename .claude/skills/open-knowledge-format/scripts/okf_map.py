#!/usr/bin/env python3
"""Build a compressed, whole-vault map of an OKF vault for an LLM to read.

The map is the orientation artefact: one payload, small enough to sit in a context
window, from which a model can plan exactly which notes to fetch — turning what
would be many exploratory calls into one map read plus one batched fetch.

It is Markdown, not JSON: an OKF vault's whole premise is that a model reads it
verbatim, and prose stubs cost fewer tokens than the equivalent JSON.

What it carries, and why each part is here:
  root index.md verbatim   the human-authored orientation and reading order — OKF's
                           own progressive-disclosure entry point. Folder-level
                           indexes are NOT included: their content is a list of the
                           notes they hold, which the stubs below already give.
  vocabulary               observed `type` and `tag` histograms. This is what makes
                           a producer-defined, unenumerated schema queryable — the
                           model learns the vault's vocabulary by being shown it.
  structure                one stub per concept note, grouped by folder.
  hubs                     highest concept-degree notes — the centre of gravity.
  gaps                     broken links and unreferenced counts, so a reader knows
                           where the vault is thin rather than trusting it blindly.

Compression stance: full vault-relative paths are printed for every stub even
though folder grouping makes prefixes redundant, because a path a model must
reassemble from a heading is a path it will get wrong. Link *targets* are shortened
to a basename only when that basename is unambiguous vault-wide, and every tool
accepts either form. Defaults (status stable, trust unverified) are omitted rather
than stated — most notes are all-defaults, so only deviations cost anything.

Usage:
  python3 okf_map.py <vault-dir> [--max-notes N] [--no-root-index]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_graph import (  # noqa: E402
    adjacency, basename_index, build_graph, parse_frontmatter, read_text,
    strip_frontmatter, today,
)

DEFAULT_MAX_NOTES = 400


def short_ref(rel, bindex):
    """Shortest unambiguous form of a relpath, for link targets."""
    base = os.path.basename(rel)
    return base if bindex.get(base) == rel else rel


def note_flags(node):
    """Only deviations from default: stable status, unverified trust, not stale."""
    out = []
    if node["status"] and node["status"] != "stable":
        out.append(node["status"])
    if node["trust"] != "unverified":
        out.append(node["trust"])
    if node["stale"]:
        out.append(f"stale since {node['stale_after']}")
    return f" [{', '.join(out)}]" if out else ""


def stub_lines(rel, node, out_links, bindex, with_links=True):
    """One note as map/search stub lines. Shared with the MCP server so a search
    result and a map entry are formatted identically."""
    desc = node["description"] or node["excerpt"][:120]
    line = f"- {rel} ({node['type']}){note_flags(node)}"
    if desc:
        line += f" — {desc}"
    lines = [line]
    if with_links and out_links:
        targets = ", ".join(short_ref(t, bindex) for t in out_links)
        lines.append(f"  -> {targets}")
    return lines


def build_map(vault, max_notes=DEFAULT_MAX_NOTES, root_index=True):
    nodes, edges, stats = build_graph(vault)
    out_map, in_map = adjacency(edges, nodes, concepts_only=True)
    bindex = basename_index(nodes)
    concepts = {rel: n for rel, n in nodes.items() if not n["reserved"]}

    name = os.path.basename(vault.rstrip("/")) or vault
    root_fm, _ = parse_frontmatter(read_text(os.path.join(vault, "index.md")))
    version = root_fm.get("okf_version") or "unset"

    L = []
    L.append(f"# OKF vault map: {name}")
    L.append("")
    L.append(f"okf_version {version} · {stats['concepts']} concept notes · "
             f"{stats['links']} links · mapped {today()}")
    L.append("")
    L.append("Path = identity. Every path below is fetchable verbatim with "
             "`okf_get`; link targets shown as a bare filename are unambiguous and "
             "also accepted. Stubs only — no note bodies are included here.")
    L.append("Omitted because they are defaults: `status: stable`, "
             "`trust: unverified`. Bracketed flags mark deviations.")

    # --- root index verbatim: the vault's own orientation and reading order ---
    if root_index:
        body = strip_frontmatter(read_text(os.path.join(vault, "index.md"))).strip()
        if body:
            L += ["", "## Root index (verbatim)", "", body]

    # --- vocabulary: what makes an unenumerated, producer-defined schema usable ---
    types, tags = {}, {}
    for n in concepts.values():
        types[n["type"]] = types.get(n["type"], 0) + 1
        for t in n["tags"]:
            tags[t] = tags.get(t, 0) + 1
    fmt = lambda d, k: ", ".join(f"{label} {c}" for label, c in
                                 sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:k])
    L += ["", "## Vocabulary", "",
          f"types ({len(types)}): {fmt(types, 40) or 'none'}", "",
          f"tags ({len(tags)}): {fmt(tags, 60) or 'none'}"]

    # --- structure: stubs grouped by folder, degraded by degree if oversized ---
    ranked = sorted(concepts, key=lambda r: (-concepts[r]["degree"], r))
    detailed = set(ranked[:max_notes])
    dropped = [r for r in ranked[max_notes:]]

    folders = {}
    for rel in concepts:
        folders.setdefault(os.path.dirname(rel) or ".", []).append(rel)

    L += ["", "## Structure", ""]
    for folder in sorted(folders):
        label = "(vault root)" if folder == "." else folder + "/"
        has_index = os.path.isfile(os.path.join(vault, folder, "index.md"))
        L.append(f"### {label}" + ("" if has_index else "  (no index.md)"))
        L.append("")
        for rel in sorted(folders[folder]):
            L += stub_lines(rel, concepts[rel], out_map.get(rel, []), bindex,
                            with_links=rel in detailed)
        L.append("")

    if dropped:
        L += [f"> Note: {len(dropped)} of {len(concepts)} notes are listed without "
              f"their outbound links, to keep this map within {max_notes} detailed "
              f"notes (lowest concept-degree first). Use `okf_neighbours` on any of "
              f"them to get their links.", ""]

    # --- hubs: where the graph's connectivity is concentrated ---
    hubs = [r for r in ranked[:8] if concepts[r]["degree"] > 0]
    if hubs:
        L += ["## Hubs (highest concept-degree — the vault's centre of gravity)", ""]
        for rel in hubs:
            n = concepts[rel]
            L.append(f"- {rel} — degree {n['degree']} "
                     f"({n['in_deg']} in, {n['out_deg']} out)")
        L.append("")

    # --- gaps: where not to trust the vault ---
    unref = sorted(r for r in concepts if not in_map.get(r))
    L += ["## Gaps", "",
          f"- broken internal links: {stats['broken']}",
          f"- isolated notes (no concept links at all): {stats['isolated']}",
          f"- unreferenced (no inbound link from a concept note): "
          f"{len(unref)}{' — ' + ', '.join(unref[:12]) if unref else ''}"
          + (", …" if len(unref) > 12 else ""),
          ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description="Build a compressed whole-vault map of an OKF vault.")
    ap.add_argument("vault")
    ap.add_argument("--max-notes", type=int, default=DEFAULT_MAX_NOTES,
                    help=f"notes given full detail (default {DEFAULT_MAX_NOTES})")
    ap.add_argument("--no-root-index", action="store_true",
                    help="omit the verbatim root index.md")
    args = ap.parse_args()

    vault = os.path.abspath(args.vault)
    if not os.path.isdir(vault):
        print(f"error: not a directory: {vault}", file=sys.stderr)
        return 2

    text = build_map(vault, args.max_notes, not args.no_root_index)
    print(text)
    # Sizing aid on stderr so it never pollutes the map itself. ~4 chars/token is a
    # rough English approximation, adequate for deciding whether a vault fits.
    print(f"\n[{len(text)} chars, ~{len(text) // 4} tokens]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
