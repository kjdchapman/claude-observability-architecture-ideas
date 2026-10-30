#!/usr/bin/env python3
"""Shared OKF v0.2 vault parsing and graph model. Standard library only.

The single parser for every OKF tool in this skill — the validator, the graph
viewer, and the MCP server all import from here, so their answers cannot drift
apart. Nothing in this module prints or exits; it is a library.

What it provides:
  parse_frontmatter  targeted parser for the v0.2 frontmatter shapes (not full YAML)
  trust_tier         verified[] -> unverified | machine-confirmed | human-reviewed
  collect_md_files   ordered walk of a vault's .md files, skipping dotted dirs
  clean_target /
    resolve /
    is_internal      Markdown link-target normalisation and resolution
  build_graph        vault -> (nodes, edges, stats) concept-degree graph model
  adjacency          edges -> (out_map, in_map)
  prune_reserved     drop index.md/log.md nodes from a built graph (display only)
  vault_signature    cheap mtime signature for change detection / cache invalidation

Concept-degree convention (shared by every consumer): edges touching an index.md
or log.md are navigation, not knowledge, and are excluded from degree, inbound and
outbound counts. Being listed in an index must not count as a reference.
"""

import datetime
import os
import re

RESERVED = {"index.md", "log.md"}
MD_LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")  # [text](target), not images
ISO_TS = re.compile(
    r"^\d{4}-\d{2}-\d{2}"  # date
    r"([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?"  # optional time
    r"(Z|[+-]\d{2}:?\d{2})?)?$"  # optional tz
)
URL = re.compile(r"^https?://", re.IGNORECASE)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# actor convention: human:<id> | process:<id> | <prefix>:<id> | <producer>/<version>
ACTOR = re.compile(r"^([A-Za-z0-9_.-]+:.+|[^/\s]+/[^/\s]+)$")
STATUSES = {"draft", "stable", "deprecated"}


def today():
    """Today as YYYY-MM-DD. A function, not a constant: the graph server and the
    MCP server are long-lived, so a module-level date would go stale overnight and
    quietly mis-report `stale_after`."""
    return datetime.date.today().isoformat()


# --- frontmatter parsing (targeted for the v0.2 field shapes; not full YAML) ---

def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        v = v[1:-1]
    return v


def _inline_map(s):
    """Parse `{ a: b, c: d }` (OKF trust maps have no nested commas)."""
    s = s.strip()
    if s.startswith("{"):
        s = s[1:]
    if s.endswith("}"):
        s = s[:-1]
    out = {}
    for part in s.split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = _scalar(v)
    return out


def _map_from(inline, sub):
    inline = inline.strip()
    if inline.startswith("{"):
        return _inline_map(inline)
    out = {}
    for l in sub:
        s = l.strip()
        if not s or s.startswith("#"):
            continue
        if ":" in s:
            k, v = s.split(":", 1)
            out[k.strip()] = _scalar(v)
    return out or None


def _list_of_maps(inline, sub):
    inline = inline.strip()
    if inline.startswith("{"):            # single bare mapping
        return [_inline_map(inline)]
    if inline.startswith("["):            # inline list of maps
        return [_inline_map(p) for p in re.findall(r"\{[^}]*\}", inline)]
    items, cur, saw_dash = [], None, False
    for l in sub:
        s = l.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("-"):
            saw_dash = True
            body = s[1:].strip()
            if body.startswith("{"):
                items.append(_inline_map(body))
                cur = None
            else:
                cur = {}
                if ":" in body:
                    k, v = body.split(":", 1)
                    cur[k.strip()] = _scalar(v)
                items.append(cur)
        elif cur is not None and ":" in s:
            k, v = s.split(":", 1)
            cur[k.strip()] = _scalar(v)
    if not saw_dash:                      # single block mapping, no leading dash
        m = {}
        for l in sub:
            s = l.strip()
            if s and not s.startswith("#") and ":" in s:
                k, v = s.split(":", 1)
                m[k.strip()] = _scalar(v)
        if m:
            return [m]
    return items


def _frontmatter_block(text):
    """Return (block_lines, closed). block_lines is None when no block opens."""
    if not text.startswith("---"):
        return None, False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, False
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], True
    return lines[1:], False  # opened but never closed


def _top_blocks(lines):
    """Split frontmatter into (key, inline_value, sub_lines) entries at indent 0."""
    blocks, i = [], 0
    while i < len(lines):
        l = lines[i]
        if not l.strip() or l.lstrip().startswith("#") or l[0] in " \t":
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s?(.*)$", l)
        if not m:
            i += 1
            continue
        key, inline = m.group(1), m.group(2)
        sub, j = [], i + 1
        while j < len(lines):
            l2 = lines[j]
            if l2.strip() and l2[0] not in " \t":
                break
            sub.append(l2)
            j += 1
        blocks.append((key, inline, sub))
        i = j
    return blocks


def parse_frontmatter(text):
    """Return (frontmatter_dict, closed).

    Scalars are strings; `generated` is a dict (or None); `verified`/`sources` are
    lists of dicts. Targeted stdlib parser for the v0.2 shapes, not general YAML.
    """
    block, closed = _frontmatter_block(text)
    if block is None:
        return {}, False
    fm = {}
    for key, inline, sub in _top_blocks(block):
        if key == "generated":
            fm["generated"] = _map_from(inline, sub)
        elif key in ("verified", "sources"):
            fm[key] = _list_of_maps(inline, sub)
        else:
            fm[key] = _scalar(inline)
    return fm, closed


def trust_tier(verified):
    if not verified:
        return "unverified"
    if any(str(v.get("by", "")).startswith("human:") for v in verified):
        return "human-reviewed"
    return "machine-confirmed"


def parse_tags(raw):
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip().strip("\"'") for t in raw.split(",") if t.strip()]


def body_excerpt(text, limit=220):
    """First prose of the body, frontmatter and headings stripped."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
        if len(" ".join(out)) >= limit:
            break
    excerpt = " ".join(out)
    return excerpt[:limit] + ("…" if len(excerpt) > limit else "")


def strip_frontmatter(text):
    """The body only, frontmatter block removed."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n")
    return text


# --- vault walk & link resolution -------------------------------------------

def collect_md_files(vault):
    out = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.join(root, f))
    return sorted(out)


def clean_target(raw):
    """Normalise a Markdown link target: strip title, angle brackets, anchor."""
    t = raw.strip()
    if t.startswith("<") and ">" in t:
        t = t[1:t.index(">")]
    else:
        t = t.split()[0] if t.split() else t  # drop optional "title"
    t = t.split("#", 1)[0]  # drop anchor
    return t.strip()


def resolve(target, source_file, vault):
    """Resolve a cleaned internal target to an absolute path (unchecked)."""
    if target.startswith("/"):
        return os.path.normpath(os.path.join(vault, target.lstrip("/")))
    return os.path.normpath(os.path.join(os.path.dirname(source_file), target))


def is_internal(target):
    return bool(target) and not URL.match(target) and not target.startswith(
        ("mailto:", "tel:", "#")
    )


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


# --- graph model -------------------------------------------------------------

def build_graph(vault):
    """Parse a vault into (nodes, edges, stats).

    nodes: {relpath: node dict}; edges: sorted unique [(src_rel, dst_rel)] over
    resolvable internal links. Degree/in_deg/out_deg are concept-only (see module
    docstring). Unresolvable links are counted in stats["broken"], not represented.
    """
    files = collect_md_files(vault)
    fileset = set(files)
    now = today()
    nodes = {}
    edges = []
    broken = 0
    for path in files:
        rel = os.path.relpath(path, vault)
        base = os.path.basename(path)
        text = read_text(path)
        fm, _ = parse_frontmatter(text)
        reserved = base in RESERVED
        ntype = ("index" if base == "index.md" else "log") if reserved else (
            fm.get("type") or "untyped")
        gen = fm.get("generated") if isinstance(fm.get("generated"), dict) else None
        gen_at = (gen.get("at") if gen else None) or fm.get("timestamp", "")
        verified = fm.get("verified") or []
        sa = fm.get("stale_after")
        nodes[rel] = {
            "id": rel,
            "type": ntype,
            "title": fm.get("title") or rel,
            "description": fm.get("description", ""),
            "tags": parse_tags(fm.get("tags", "")),
            "timestamp": gen_at,
            "reserved": reserved,
            "excerpt": body_excerpt(text),
            "trust": "unverified" if reserved else trust_tier(verified),
            "status": "" if reserved else (fm.get("status") or "stable"),
            "stale": bool(sa and DATE.match(sa) and sa <= now),
            "stale_after": sa or "",
            "generated": gen or {},
            "verified": verified,
            "sources": fm.get("sources") or [],
            "resource": fm.get("resource", ""),
            "search": " ".join([
                rel, ntype, fm.get("title", ""), fm.get("description", ""),
                fm.get("tags", ""), text,
            ]).lower(),
            "degree": 0,
        }
        for m in MD_LINK.finditer(text):
            tgt = clean_target(m.group(1))
            if not is_internal(tgt):
                continue
            r = resolve(tgt, path, vault)
            dest = r if r in fileset else (r + ".md" if r + ".md" in fileset else None)
            if dest is None:
                broken += 1
                continue
            drel = os.path.relpath(dest, vault)
            if drel != rel:
                edges.append((rel, drel))

    # Degree over the CONCEPT-ONLY subgraph: edges touching an index/log node are
    # navigation, not knowledge, so they are excluded from sizing/connectivity.
    edges = sorted(set(edges))
    for n in nodes.values():
        n["degree"] = n["in_deg"] = n["out_deg"] = 0
    for a, b in edges:
        na, nb = nodes.get(a), nodes.get(b)
        if not na or not nb or na["reserved"] or nb["reserved"]:
            continue
        na["degree"] += 1
        nb["degree"] += 1
        na["out_deg"] += 1
        nb["in_deg"] += 1

    concepts = sum(1 for n in nodes.values() if not n["reserved"])
    isolated = sum(1 for n in nodes.values()
                   if n["degree"] == 0 and not n["reserved"])
    unreferenced = sum(1 for n in nodes.values()
                       if n["in_deg"] == 0 and not n["reserved"])
    return nodes, edges, {"concepts": concepts, "links": len(edges),
                          "isolated": isolated, "unreferenced": unreferenced,
                          "broken": broken}


def adjacency(edges, nodes=None, concepts_only=False):
    """edges -> (out_map, in_map) of relpath -> sorted list of relpaths.

    concepts_only drops edges touching a reserved index/log node, matching the
    concept-degree convention. Requires `nodes` when set.
    """
    out_map, in_map = {}, {}
    for a, b in edges:
        if concepts_only and nodes is not None:
            na, nb = nodes.get(a), nodes.get(b)
            if not na or not nb or na["reserved"] or nb["reserved"]:
                continue
        out_map.setdefault(a, []).append(b)
        in_map.setdefault(b, []).append(a)
    return ({k: sorted(v) for k, v in out_map.items()},
            {k: sorted(v) for k, v in in_map.items()})


def basename_index(nodes):
    """basename -> relpath, only where that basename is unambiguous in the vault.

    Lets the map print short link targets and lets the MCP tools accept them, so a
    caller never has to reassemble folder + filename — the one reassembly step that
    a model reliably gets wrong.
    """
    seen = {}
    for rel in nodes:
        seen.setdefault(os.path.basename(rel), []).append(rel)
    return {b: v[0] for b, v in seen.items() if len(v) == 1}


def resolve_ref(ref, nodes, bindex=None):
    """Resolve a caller-supplied note reference to a relpath key of `nodes`, or None.

    Accepts a vault-relative path (leading slash optional, `.md` optional) or an
    unambiguous basename.
    """
    if ref in nodes:
        return ref
    r = ref.strip().lstrip("/")
    for cand in (r, r + ".md"):
        if cand in nodes:
            return cand
    bindex = basename_index(nodes) if bindex is None else bindex
    for cand in (r, r + ".md"):
        if cand in bindex:
            return bindex[cand]
    return None


def prune_reserved(nodes, edges, stats):
    """Drop reserved index.md/log.md nodes and edges touching them (display only).
    Concept degree/in/out were already computed concept-only, so they carry over."""
    keep = {rel: n for rel, n in nodes.items() if not n["reserved"]}
    kept = [(a, b) for a, b in edges if a in keep and b in keep]
    return keep, kept, dict(stats, links=len(kept))


def vault_signature(vault):
    """Cheap change signature: sorted (relpath, mtime) of every .md file."""
    sig = []
    for p in collect_md_files(vault):
        try:
            sig.append((os.path.relpath(p, vault), os.stat(p).st_mtime_ns))
        except OSError:
            pass
    return tuple(sig)
