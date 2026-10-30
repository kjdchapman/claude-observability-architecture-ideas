#!/usr/bin/env python3
"""Read-only MCP server exposing OKF vaults over stdio. Standard library only.

Why this exists: an API-based or otherwise remote model cannot walk a directory,
so it needs an interface. This is that interface — and it is deliberately shaped so
the common case costs *one* round trip: read the vault map (as an MCP resource the
client can attach before the first turn, or as a tool call), then fetch the handful
of notes the map identified in a single batched `okf_get`.

Transport is stdio with newline-delimited JSON-RPC 2.0, hand-rolled rather than
taken from the MCP SDK, because the method surface here is small and this plugin's
zero-dependency property is load-bearing for its portability claim. The server is
local to whoever runs the tool loop; nothing is hosted and nothing is authenticated.
If a third party's client ever needs to reach a vault directly, that is the point to
take the SDK dependency and an HTTP transport — not before.

Read-only by construction: there is no tool that writes, and note content is only
ever read from paths discovered by walking the configured vault, so a caller cannot
address a file outside it.

Vault discovery, in precedence order:
  1. --vault name=/path  (repeatable; bare --vault /path is named after its
     directory). Opts out of everything below — explicit intent is never overridden,
     and never silently falls back if it fails to resolve.
  2. .claude/okf.json, an optional project config with a "vault" field. Searched
     for at $CLAUDE_PROJECT_DIR and the working directory, then upward from those to
     $HOME, so a server launched in a subdirectory still finds its project.
  3. Auto-detection: any directory at a project root, or one level below it, holding
     both index.md and log.md. OKF's reserved filenames make a bundle
     self-identifying, so a project with a vault and no configuration at all just
     works. Disable with --no-autodetect.
A config file that exists is authoritative, including `enabled: false` — detection
fills a silence, it does not overrule a decision.

Discovery re-runs on every request rather than once at startup, so creating a vault
or writing the config mid-session takes effect without a restart. A server that stayed
empty for the rest of a session because it launched a moment too early would just
look broken.

Usage:
  python3 okf_mcp.py [--vault [name=]path ...] [--max-notes N]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from okf_graph import (  # noqa: E402
    adjacency, basename_index, build_graph, read_text, resolve_ref,
    strip_frontmatter, vault_signature,
)
from okf_map import (  # noqa: E402
    DEFAULT_MAX_NOTES, build_map, short_ref, stub_lines,
)
from validate_okf import build_report  # noqa: E402

SERVER_NAME = "okf"
SERVER_VERSION = "0.2.0"
# Revisions this surface (tools + resources, no sampling/roots/subscriptions) works
# identically under. A client's requested version is echoed when recognised, so a
# newer client is not rejected over a version string.
KNOWN_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
FALLBACK_PROTOCOL = KNOWN_PROTOCOLS[0]

MAX_GET_PATHS = 50
MAX_RESPONSE_CHARS = 400_000
GENERATED = ("_map", "_index", "_vocab")
# Never treated as candidate vault directories during auto-detection.
SKIP_DIRS = {"node_modules", "venv", ".venv", "vendor", "target", "dist", "build",
             "__pycache__", "site-packages", "tmp", "coverage"}

INSTRUCTIONS = """\
Each vault here is an Open Knowledge Format (OKF v0.2) bundle: a directory of \
Markdown notes with YAML frontmatter, where a note's file path IS its identity and \
relationships are ordinary Markdown links — directed but untyped, so a link asserts \
relatedness and nothing more.

To use a vault efficiently, in this order:
1. Read the `okf://<vault>/_map` resource, or call `okf_map`. It is a whole-vault \
digest: every note's path, type, one-line description, trust/lifecycle flags and \
outbound links. It exists so you can decide what is relevant WITHOUT exploring.
2. Fetch what you need in ONE batched `okf_get` call, not several.
3. Use `okf_neighbours` for inbound links (backlinks), which the map does not list, \
or to walk more than one hop.
4. Use `okf_search` when a vault is too large for the map to have detailed every \
note, or to filter by type/tag/trust.

Types and tags are producer-defined free strings, not a fixed enum — the map's \
Vocabulary section lists the ones this vault actually uses. Trust signals are worth \
heeding: `human-reviewed` beats `machine-confirmed` beats unverified, and a note \
flagged stale or deprecated should be reported as such rather than stated as fact.

To check a vault's integrity rather than read it, call `okf_validate` — do not go \
looking for a validator script on the host, as there is no path you can rely on.

Everything here is read-only: no tool in this server can modify a vault.\
"""


# --- vault registry with mtime-invalidated cache -----------------------------

class Vault:
    """A configured vault and its cached graph, rebuilt when any .md file changes."""

    def __init__(self, name, path, source="explicit"):
        self.name = name
        self.path = path
        self.source = source  # explicit | config | auto-detected, for diagnostics
        self._sig = None
        self._cache = None

    def graph(self):
        sig = vault_signature(self.path)
        if sig != self._sig or self._cache is None:
            nodes, edges, stats = build_graph(self.path)
            out_map, in_map = adjacency(edges, nodes, concepts_only=True)
            self._cache = {
                "nodes": nodes, "edges": edges, "stats": stats,
                "out": out_map, "in": in_map,
                "bindex": basename_index(nodes),
                "concepts": {r: n for r, n in nodes.items() if not n["reserved"]},
            }
            self._sig = sig
        return self._cache


VAULTS = {}
MAX_NOTES = DEFAULT_MAX_NOTES
# True when --vault was passed: the registry is then fixed at startup and neither
# config nor auto-detection is consulted, so explicit intent is never overridden.
EXPLICIT_VAULTS = False
AUTODETECT = True
_WARNED = set()


def warn_once(message):
    """stderr diagnostics, deduplicated — discovery runs on every request, so an
    unchanged problem must not produce an unbounded stream of identical warnings."""
    if message not in _WARNED:
        _WARNED.add(message)
        print(f"okf-mcp: {message}", file=sys.stderr)


def refresh_vaults():
    """Rediscover vaults, reusing Vault objects whose path has not changed.

    Runs before every vault-dependent request rather than once at startup, because
    a project can gain a vault or a config mid-session and a server that stayed
    empty for the rest of that session would simply look broken. Costs a
    handful of stats — trivial beside the per-request mtime scan of the vault itself.
    """
    if EXPLICIT_VAULTS:
        return
    found = vaults_from_config()
    if found is None:  # no config file at all — fall back to detection
        found = autodetect_vaults() if AUTODETECT else {}
    for name in [n for n in VAULTS
                 if n not in found or VAULTS[n].path != found[n].path]:
        del VAULTS[name]
    for name, v in found.items():
        VAULTS.setdefault(name, v)  # keep the existing graph cache where unchanged


def pick_vault(name):
    """Resolve a vault argument. Optional when exactly one vault is configured."""
    if not VAULTS:
        looked = ", ".join(project_roots()) or "the working directory"
        raise ValueError(
            f"no vaults are configured, and none was auto-detected in {looked} or "
            f"one level below it. An OKF vault is a directory containing both "
            f"index.md and log.md. This is a configuration gap, not a fault: the "
            f"vault can still be read from disk directly. To register it, either "
            f"add a \"vault\" field to .claude/okf.json (which takes effect "
            f"without a restart), or start this server with "
            f"--vault name=/path/to/vault.")
    if name:
        if name not in VAULTS:
            raise ValueError(f"unknown vault {name!r}. Configured: "
                             f"{', '.join(sorted(VAULTS))}")
        return VAULTS[name]
    if len(VAULTS) == 1:
        return next(iter(VAULTS.values()))
    raise ValueError(f"several vaults are configured, so `vault` is required: "
                     f"{', '.join(sorted(VAULTS))}")


def need_note(g, ref):
    rel = resolve_ref(ref, g["nodes"], g["bindex"])
    if rel is None:
        raise ValueError(
            f"no note matches {ref!r}. Give a vault-relative path as shown in the "
            f"map (e.g. vendors/acme-cdp.md), or an unambiguous filename.")
    return rel


def clip(text, note):
    """Never truncate silently — a caller must know the answer is partial."""
    if len(text) <= MAX_RESPONSE_CHARS:
        return text
    return (text[:MAX_RESPONSE_CHARS]
            + f"\n\n[TRUNCATED at {MAX_RESPONSE_CHARS} characters. {note}]")


# --- tools -------------------------------------------------------------------

def tool_okf_map(args):
    v = pick_vault(args.get("vault"))
    return build_map(v.path, int(args.get("max_notes") or MAX_NOTES))


def tool_okf_get(args):
    v = pick_vault(args.get("vault"))
    g = v.graph()
    paths = args.get("paths") or []
    if isinstance(paths, str):
        paths = [paths]
    if not paths:
        raise ValueError("`paths` is required — pass one or more note paths, "
                         "batched into this single call.")
    extra = ""
    if len(paths) > MAX_GET_PATHS:
        extra = (f"\n\n[{len(paths) - MAX_GET_PATHS} further paths were not "
                 f"fetched: this tool returns at most {MAX_GET_PATHS} notes per "
                 f"call. Call it again for the rest.]")
        paths = paths[:MAX_GET_PATHS]

    want_body = args.get("include_body", True)
    out = []
    for ref in paths:
        try:
            rel = need_note(g, ref)
        except ValueError as e:
            out.append(f"=== {ref} ===\nNOT FOUND. {e}")
            continue
        n = g["nodes"][rel]
        head = [f"=== {rel} ==="]
        bits = [f"type: {n['type']}", f"trust: {n['trust']}"]
        if n["status"]:
            bits.append(f"status: {n['status']}")
        if n["stale"]:
            bits.append(f"STALE since {n['stale_after']}")
        bits.append(f"concept-degree {n['degree']} "
                    f"({n['in_deg']} in, {n['out_deg']} out)")
        head.append(" · ".join(bits))
        inb = g["in"].get(rel, [])
        outb = g["out"].get(rel, [])
        # Inbound links are the value a bare file read cannot give.
        head.append("inbound (who points here): "
                    + (", ".join(short_ref(r, g["bindex"]) for r in inb) or "none"))
        head.append("outbound: "
                    + (", ".join(short_ref(r, g["bindex"]) for r in outb) or "none"))
        block = "\n".join(head)
        if want_body:
            block += "\n\n" + read_text(os.path.join(v.path, rel)).rstrip()
        out.append(block)
    return clip("\n\n".join(out), "Fetch fewer paths per call.") + extra


def tool_okf_neighbours(args):
    v = pick_vault(args.get("vault"))
    g = v.graph()
    rel = need_note(g, args.get("path") or "")
    depth = max(1, min(3, int(args.get("depth") or 1)))
    direction = (args.get("direction") or "both").lower()
    if direction not in ("in", "out", "both"):
        raise ValueError("`direction` must be one of: in, out, both")

    frontier, seen, rings = {rel}, {rel}, []
    for _ in range(depth):
        nxt = set()
        for cur in frontier:
            if direction in ("out", "both"):
                nxt |= set(g["out"].get(cur, []))
            if direction in ("in", "both"):
                nxt |= set(g["in"].get(cur, []))
        nxt -= seen
        if not nxt:
            break
        seen |= nxt
        rings.append(sorted(nxt))
        frontier = nxt

    n = g["nodes"][rel]
    L = [f"# Neighbourhood of {rel}",
         f"{n['type']} · {n['trust']} · concept-degree {n['degree']} "
         f"({n['in_deg']} in, {n['out_deg']} out) · direction {direction}, "
         f"depth {depth}"]
    if not rings:
        L += ["", "No linked concept notes — this note is isolated in the concept "
                  "graph. (Links to or from index.md/log.md are navigation and are "
                  "excluded by design.)"]
    for i, ring in enumerate(rings, 1):
        L += ["", f"## {i} hop{'s' if i > 1 else ''} away ({len(ring)})", ""]
        for r in ring:
            L += stub_lines(r, g["nodes"][r], g["out"].get(r, []), g["bindex"])
    L += ["", "## Edges in this neighbourhood", ""]
    scope = seen
    for a, b in g["edges"]:
        if a in scope and b in scope and not g["nodes"][a]["reserved"] \
                and not g["nodes"][b]["reserved"]:
            L.append(f"- {a} -> {b}")
    return clip("\n".join(L), "Reduce `depth`.")


def tool_okf_search(args):
    v = pick_vault(args.get("vault"))
    g = v.graph()
    query = (args.get("query") or "").strip().lower()
    terms = query.split()
    want_type = (args.get("type") or "").strip().lower()
    want_tags = [t.strip().lower() for t in (args.get("tags") or []) if t.strip()]
    want_status = (args.get("status") or "").strip().lower()
    want_trust = (args.get("trust") or "").strip().lower()
    stale_only = bool(args.get("stale_only"))
    limit = max(1, min(200, int(args.get("limit") or 25)))

    scored = []
    for rel, n in g["concepts"].items():
        if want_type and n["type"].lower() != want_type:
            continue
        if want_status and (n["status"] or "stable").lower() != want_status:
            continue
        if want_trust and n["trust"].lower() != want_trust:
            continue
        if stale_only and not n["stale"]:
            continue
        tags = [t.lower() for t in n["tags"]]
        if want_tags and not all(t in tags for t in want_tags):
            continue
        score = 0
        if terms:
            # AND over terms: every term must appear somewhere in the note.
            if not all(t in n["search"] for t in terms):
                continue
            title, desc = n["title"].lower(), n["description"].lower()
            for t in terms:
                score += (8 if t in title else 0) + (4 if t in desc else 0)
                score += (3 if any(t in tag for tag in tags) else 0)
                score += (2 if t in rel.lower() else 0) + 1
        scored.append((-score, -n["degree"], rel))
    scored.sort()
    hits = scored[:limit]

    crit = [c for c in (
        f"query {query!r}" if query else "",
        f"type={want_type}" if want_type else "",
        f"tags={'+'.join(want_tags)}" if want_tags else "",
        f"status={want_status}" if want_status else "",
        f"trust={want_trust}" if want_trust else "",
        "stale only" if stale_only else "") if c]
    L = [f"# Search: {' · '.join(crit) or 'all concept notes'}",
         f"{len(scored)} matched, showing {len(hits)} "
         f"(ranked by relevance, then concept-degree)", ""]
    if not hits:
        L.append("No notes matched. Types and tags are producer-defined — check the "
                 "Vocabulary section of `okf_map` for the values this vault uses.")
    for _, _, rel in hits:
        L += stub_lines(rel, g["nodes"][rel], g["out"].get(rel, []), g["bindex"])
    if len(scored) > len(hits):
        L += ["", f"[{len(scored) - len(hits)} further matches not shown; raise "
                  f"`limit` or narrow the criteria.]"]
    return clip("\n".join(L), "Lower `limit`.")


def tool_okf_validate(args):
    v = pick_vault(args.get("vault"))
    text, code = build_report(v.path, quiet=bool(args.get("quiet")),
                              strict_links=bool(args.get("strict_links")))
    # Deliberately does not name a report section: `quiet` suppresses them all, and
    # pointing at a section that isn't there is worse than saying less.
    verdict = "no hard failures" if code == 0 else "hard failures present"
    return f"{text}\n\n[validator exit code {code}: {verdict}]"


def _vault_prop():
    """A `vault` property whose enum is the vaults this server actually has, so a
    caller cannot invent a name."""
    prop = {"type": "string",
            "description": "Which configured vault to query."
                           + (" Optional — only one is configured."
                              if len(VAULTS) == 1 else "")}
    if VAULTS:
        prop["enum"] = sorted(VAULTS)
    return prop


def tool_specs():
    return [
        {
            "name": "okf_map",
            "description":
                "START HERE. Returns a whole-vault map: every concept note's path, "
                "type, one-line description, trust/lifecycle flags and outbound "
                "links, plus the vault's root index verbatim, its observed type and "
                "tag vocabulary, its hub notes and its gaps. Designed so you can "
                "choose exactly which notes to read without exploring — follow it "
                "with a single batched okf_get. Stubs only; no note bodies.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "vault": _vault_prop(),
                    "max_notes": {
                        "type": "integer",
                        "description": f"Notes given full detail, highest "
                                       f"concept-degree first (default "
                                       f"{MAX_NOTES}). The rest are still listed, "
                                       f"without their outbound links.",
                    },
                },
            },
        },
        {
            "name": "okf_get",
            "description":
                "Fetch whole notes verbatim, with their inbound links (backlinks), "
                "outbound links and degree — context a plain file read cannot give. "
                "Batch every note you need into ONE call. Accepts vault-relative "
                "paths as shown in the map, or unambiguous filenames.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Note paths, e.g. "
                                       "[\"vendors/acme-cdp.md\", \"uk-gdpr.md\"].",
                    },
                    "vault": _vault_prop(),
                    "include_body": {
                        "type": "boolean",
                        "description": "Include note bodies (default true). Set "
                                       "false for link structure only.",
                    },
                },
                "required": ["paths"],
            },
        },
        {
            "name": "okf_neighbours",
            "description":
                "Walk the link graph around one note, up to 3 hops, inbound "
                "and/or outbound. Use this for backlinks — who points AT a note — "
                "which the map does not list. Links are untyped: an edge asserts "
                "relatedness, nothing more.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string",
                             "description": "The note to walk from."},
                    "vault": _vault_prop(),
                    "depth": {"type": "integer",
                              "description": "Hops to follow, 1-3 (default 1)."},
                    "direction": {
                        "type": "string",
                        "enum": ["in", "out", "both"],
                        "description": "'in' = backlinks only, 'out' = outbound "
                                       "only, 'both' (default).",
                    },
                },
                "required": ["path"],
            },
        },
        {
            "name": "okf_search",
            "description":
                "Find concept notes by text and/or by frontmatter facet. Returns "
                "ranked stubs, never bodies — follow up with okf_get. Prefer "
                "okf_map first on a vault small enough to map fully; use this when "
                "the map is truncated or when filtering by facet. `type` and `tags` "
                "are producer-defined free strings: take their values from the "
                "map's Vocabulary section.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Free text; all words must appear. "
                                             "Matches title, description, tags, "
                                             "path and body."},
                    "vault": _vault_prop(),
                    "type": {"type": "string",
                             "description": "Exact `type` match, case-insensitive."},
                    "tags": {"type": "array", "items": {"type": "string"},
                             "description": "Notes carrying ALL of these tags."},
                    "status": {"type": "string",
                               "enum": ["draft", "stable", "deprecated"],
                               "description": "Lifecycle status (absent ⇒ stable)."},
                    "trust": {"type": "string",
                              "enum": ["unverified", "machine-confirmed",
                                       "human-reviewed"],
                              "description": "Trust tier from the `verified` field."},
                    "stale_only": {"type": "boolean",
                                   "description": "Only notes past `stale_after`."},
                    "limit": {"type": "integer",
                              "description": "Max results, 1-200 (default 25)."},
                },
            },
        },
        {
            "name": "okf_validate",
            "description":
                "Check a vault's integrity and return the report: frontmatter, "
                "broken internal links, connectivity (which notes are unreferenced "
                "versus unreachable), trust/provenance/lifecycle signals, hub "
                "outliers with their removal impact, and stale notes. Reports only "
                "— it modifies nothing. A missing or empty `type` or `description` "
                "is a hard failure; broken links are warnings, which OKF tolerates "
                "by design. Use this instead of looking for a validator script on "
                "the host: there isn't a path you can rely on finding.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "vault": _vault_prop(),
                    "quiet": {"type": "boolean",
                              "description": "Summary counts only, without the "
                                             "per-note detail (default false)."},
                    "strict_links": {
                        "type": "boolean",
                        "description": "Also treat broken internal links as a "
                                       "failure in the reported exit code.",
                    },
                },
            },
        },
    ]


TOOLS = {
    "okf_map": tool_okf_map,
    "okf_get": tool_okf_get,
    "okf_neighbours": tool_okf_neighbours,
    "okf_search": tool_okf_search,
    "okf_validate": tool_okf_validate,
}


# --- resources ---------------------------------------------------------------

def resource_specs():
    """A handful of concrete resources per vault. Notes are NOT enumerated — a
    large vault would flood resources/list and invite clients to attach all of it;
    they are reachable through the URI template instead."""
    out = []
    for name in sorted(VAULTS):
        out += [
            {"uri": f"okf://{name}/_map",
             "name": f"{name}: vault map",
             "description": "Whole-vault digest — every note's path, type, "
                            "description, trust flags and outbound links. Read this "
                            "first; it is built to make exploration unnecessary.",
             "mimeType": "text/markdown"},
            {"uri": f"okf://{name}/_index",
             "name": f"{name}: root index",
             "description": "The vault's own root index.md verbatim — what it is, "
                            "how it is organised, suggested reading order.",
             "mimeType": "text/markdown"},
            {"uri": f"okf://{name}/_vocab",
             "name": f"{name}: vocabulary",
             "description": "Observed `type` and tag values with counts. The "
                            "cheap orientation for a vault too large to map fully.",
             "mimeType": "text/markdown"},
        ]
    return out


def resource_templates():
    return [{
        "uriTemplate": "okf://{vault}/{path}",
        "name": "OKF note",
        "description": "Any note in a vault, verbatim, by its vault-relative path — "
                       "e.g. okf://myvault/vendors/acme-cdp.md. Path is identity in "
                       "OKF, so the URI is the note's identifier.",
        "mimeType": "text/markdown",
    }]


def build_vocab(v):
    g = v.graph()
    types, tags = {}, {}
    for n in g["concepts"].values():
        types[n["type"]] = types.get(n["type"], 0) + 1
        for t in n["tags"]:
            tags[t] = tags.get(t, 0) + 1
    order = lambda d: sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
    L = [f"# Vocabulary: {v.name}", "",
         f"{g['stats']['concepts']} concept notes. `type` and tag values are "
         f"producer-defined, not a fixed enum — these are the ones in use.", "",
         f"## Types ({len(types)})", ""]
    L += [f"- {t} — {c}" for t, c in order(types)]
    L += ["", f"## Tags ({len(tags)})", ""]
    L += [f"- {t} — {c}" for t, c in order(tags)] or ["(none)"]
    return "\n".join(L)


def read_resource(uri):
    if not uri.startswith("okf://"):
        raise ValueError(f"unsupported URI scheme: {uri!r} (expected okf://)")
    rest = uri[len("okf://"):]
    vname, _, path = rest.partition("/")
    v = pick_vault(vname or None)
    if not path or path == "_map":
        return build_map(v.path, MAX_NOTES)
    if path == "_index":
        body = read_text(os.path.join(v.path, "index.md"))
        if not body:
            raise ValueError(f"vault {v.name!r} has no root index.md")
        return body
    if path == "_vocab":
        return build_vocab(v)
    g = v.graph()
    rel = need_note(g, path)
    return read_text(os.path.join(v.path, rel))


# --- JSON-RPC over stdio -----------------------------------------------------

def handle(msg):
    """Return a response dict, or None for a notification."""
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}
    is_notification = mid is None
    # Before anything vault-dependent, including tools/list — its `vault` enum is
    # built from the live registry. A client that cached tools/list while there were
    # no vaults keeps a schema with no enum, which still works: `vault` is optional
    # whenever exactly one vault is configured.
    refresh_vaults()

    def ok(result):
        return None if is_notification else {
            "jsonrpc": "2.0", "id": mid, "result": result}

    def err(code, message):
        return None if is_notification else {
            "jsonrpc": "2.0", "id": mid,
            "error": {"code": code, "message": message}}

    if method == "initialize":
        want = params.get("protocolVersion")
        return ok({
            "protocolVersion": want if want in KNOWN_PROTOCOLS else FALLBACK_PROTOCOL,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return ok({})
    if method and method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return ok({"tools": tool_specs()})
    if method == "resources/list":
        return ok({"resources": resource_specs()})
    if method == "resources/templates/list":
        return ok({"resourceTemplates": resource_templates()})
    if method == "resources/read":
        uri = params.get("uri") or ""
        try:
            text = read_resource(uri)
        except ValueError as e:
            return err(-32602, str(e))
        except Exception as e:  # unreadable vault, permissions, ...
            return err(-32603, f"could not read {uri}: {e}")
        return ok({"contents": [{"uri": uri, "mimeType": "text/markdown",
                                 "text": clip(text, "")}]})
    if method == "tools/call":
        name = params.get("name")
        fn = TOOLS.get(name)
        if fn is None:
            return err(-32602, f"unknown tool {name!r}. Available: "
                               f"{', '.join(sorted(TOOLS))}")
        try:
            text = fn(params.get("arguments") or {})
        except Exception as e:
            # A tool failure is a result the model must see and recover from, not a
            # protocol error, so it comes back as isError content.
            return ok({"content": [{"type": "text", "text": f"Error: {e}"}],
                       "isError": True})
        return ok({"content": [{"type": "text", "text": text}], "isError": False})

    return err(-32601, f"method not found: {method!r}")


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            out = {"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": f"parse error: {e}"}}
        else:
            if isinstance(msg, list):  # batch
                responses = [r for r in (handle(m) for m in msg) if r]
                out = responses or None
            else:
                try:
                    out = handle(msg)
                except Exception as e:  # never let one bad request kill the loop
                    print(f"okf-mcp: unhandled error: {e}", file=sys.stderr)
                    out = {"jsonrpc": "2.0", "id": msg.get("id"),
                           "error": {"code": -32603, "message": str(e)}}
        if out is not None:
            # One JSON object per line: stdout is the transport, so nothing else
            # may ever be written to it.
            stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            stdout.flush()


def vaults_from_specs(specs):
    """--vault entries, each `[name=]path`."""
    found = {}
    for spec in specs or []:
        name, sep, path = spec.partition("=")
        if not sep or os.sep in name or not name:
            name, path = "", spec
        path = os.path.abspath(os.path.expanduser(path))
        name = name or (os.path.basename(path.rstrip(os.sep)) or "vault")
        if not os.path.isdir(path):
            print(f"okf-mcp: skipping {name}: not a directory: {path}",
                  file=sys.stderr)
            continue
        found[name] = Vault(name, path)
    return found


def project_roots():
    """Where to look for configuration and vaults, best candidate first.

    CLAUDE_PROJECT_DIR when the harness provides it, then the working directory.
    Both, because an MCP server's cwd is whatever launched it and is not guaranteed
    to be the project — assuming otherwise is what made correctly-configured vaults
    invisible.
    """
    roots, seen = [], set()
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), os.getcwd()):
        if not candidate:
            continue
        path = os.path.abspath(os.path.expanduser(candidate))
        if path not in seen and os.path.isdir(path):
            seen.add(path)
            roots.append(path)
    return roots


def config_path():
    """The nearest .claude/okf.json at or above a project root, or None.

    Walks upward so a server launched in a subdirectory still finds its project's
    config, but stops at $HOME so a stray config in a directory like ~/Code cannot
    silently capture every project beneath it.
    """
    home = os.path.abspath(os.path.expanduser("~"))
    for root in project_roots():
        current = root
        while True:
            candidate = os.path.join(current, ".claude", "okf.json")
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(current)
            if current == home or parent == current:
                break
            current = parent
    return None


def vaults_from_config():
    """Vaults declared in .claude/okf.json, or None when there is no file.

    None and {} mean different things: no file at all means "nothing was said, go
    and look", whereas a file that yields nothing is the project explicitly saying
    no — including `enabled: false`, which must not be second-guessed by detection.
    """
    cfg = config_path()
    if cfg is None:
        return None
    found = {}
    try:
        data = json.loads(read_text(cfg) or "{}")
    except json.JSONDecodeError as e:
        warn_once(f"{cfg} is not valid JSON: {e}")
        return found
    raw = data.get("vault")
    if raw and data.get("enabled", True):
        base = os.path.dirname(os.path.dirname(cfg))  # the project, not .claude
        path = os.path.abspath(raw if os.path.isabs(raw)
                               else os.path.join(base, raw))
        if os.path.isdir(path):
            name = os.path.basename(path.rstrip(os.sep)) or "vault"
            found[name] = Vault(name, path, source="config")
        else:
            warn_once(f"{cfg} points at a missing vault: {path}")
    return found


def looks_like_vault(path):
    """An OKF bundle is self-identifying: both reserved filenames are present."""
    return all(os.path.isfile(os.path.join(path, name))
               for name in ("index.md", "log.md"))


def autodetect_vaults():
    """Vaults sitting at a project root or one level below it.

    Because OKF reserves `index.md` and `log.md`, a bundle announces itself and the
    common case — a project with a vault in it and no configuration whatsoever —
    needs no setup at all. Deliberately one level deep and never up the ancestor
    chain: scanning from somewhere like ~/Code would be slow, and would attach
    vaults belonging to entirely unrelated projects.
    """
    found = {}
    for root in project_roots():
        candidates = [root]
        try:
            candidates += [os.path.join(root, entry)
                           for entry in sorted(os.listdir(root))]
        except OSError:
            pass
        for path in candidates:
            base = os.path.basename(path)
            if path != root and (base.startswith(".") or base in SKIP_DIRS):
                continue
            if not os.path.isdir(path) or not looks_like_vault(path):
                continue
            name = base or "vault"
            if name in found and found[name].path != path:
                warn_once(f"two candidate vaults are both named {name!r}; keeping "
                          f"{found[name].path} and ignoring {path}")
                continue
            found.setdefault(name, Vault(name, path, source="auto-detected"))
    return found


def main():
    ap = argparse.ArgumentParser(
        description="Read-only MCP server (stdio) exposing OKF vaults.")
    ap.add_argument("--vault", action="append", metavar="[NAME=]PATH",
                    help="a vault to expose; repeatable. Without NAME= the "
                         "directory name is used.")
    ap.add_argument("--max-notes", type=int, default=DEFAULT_MAX_NOTES,
                    help=f"notes given full detail in the map (default "
                         f"{DEFAULT_MAX_NOTES})")
    ap.add_argument("--no-autodetect", action="store_true",
                    help="do not look for vaults (a directory holding index.md and "
                         "log.md) at the project root or one level below it")
    args = ap.parse_args()

    global MAX_NOTES, EXPLICIT_VAULTS, AUTODETECT
    MAX_NOTES = args.max_notes
    AUTODETECT = not args.no_autodetect
    if args.vault:
        EXPLICIT_VAULTS = True
        VAULTS.update(vaults_from_specs(args.vault))
    else:
        refresh_vaults()
    if VAULTS:
        print("okf-mcp: serving " + ", ".join(
            f"{n} ({VAULTS[n].path}, {VAULTS[n].source})"
            for n in sorted(VAULTS)), file=sys.stderr)
    elif EXPLICIT_VAULTS:
        print("okf-mcp: no --vault resolved to a directory; tools will report this.",
              file=sys.stderr)
    else:
        print(f"okf-mcp: no vault found in {', '.join(project_roots())} — watching "
              f"for one, so creating a vault or writing .claude/okf.json takes "
              f"effect without a restart.", file=sys.stderr)
    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
