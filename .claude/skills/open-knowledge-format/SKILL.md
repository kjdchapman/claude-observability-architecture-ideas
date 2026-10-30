---
name: open-knowledge-format
description: >-
  This skill should be used when the user asks to "create an OKF vault", "scaffold
  an Open Knowledge Format vault", "add a concept/note to the OKF vault", "maintain
  or extend an OKF vault", "validate/lint/check the OKF vault", "check the links in
  the vault", "convert/restructure these notes into OKF", or to "serve/expose/query
  an OKF vault from a remote, API-based, or external model or app" (this plugin's
  read-only MCP server). It authors, maintains, validates, visualises, and serves
  Open Knowledge Format (OKF v0.2) vaults, applying proven authoring conventions and
  a bundled integrity validator. Do NOT trigger on a generic "add a note" with no OKF
  vault in play, or on requests to build knowledge on a typed graph *substrate* (a
  graph database, RDF/SPARQL, a GraphQL schema) — those are not OKF, though querying
  or serving an existing OKF vault is squarely in scope.
---

# Open Knowledge Format (OKF) authoring

Author and maintain OKF vaults *well*, not merely validly. An OKF vault is a
directory of plain Markdown files with YAML frontmatter, where relationships are
ordinary Markdown links — readable by a human with `cat`, by any Markdown tool, and
by an LLM verbatim, in any git repo with no runtime. This skill encodes the OKF v0.2
essentials, the conventions that make a vault navigable, and an integrity check, so
every vault produced is consistent, portable, and agent-consumable.

Stay **format-generic**: carry no project, customer, or domain vocabulary into a
vault. Fixed `type` enums and custom fields belong to the consuming project.

## The five rules that constrain every vault

1. A bundle is a **directory of Markdown files** — no manifest, no database.
2. **File path = concept identity.** One concept per file; never split a concept
   across files or bundle many into one. Renaming a file changes identity.
3. Every concept note has **YAML frontmatter with a required, non-empty `type`**.
4. **Reserved filenames** are not concept notes: `index.md` (navigation) and
   `log.md` (change history).
5. **Relationships are Markdown links** — a directed, untyped edge. Broken links
   are tolerated by the spec; the vault degrades gracefully.

Full distilled spec: **`references/okf-spec.md`**. The proven authoring conventions
(frontmatter discipline, the view/matrix pattern, linking, maintenance, and *when
NOT to use OKF*): **`references/conventions.md`**. Consult `conventions.md` before
authoring or restructuring — it carries good/bad examples.

## Running the bundled scripts

Every script below lives in this skill's own `scripts/` directory. Resolve
`<skill-dir>` as **the absolute directory this `SKILL.md` was loaded from** — you
already have that path, so build the script path from it.

**Do not put `$CLAUDE_PLUGIN_ROOT` in a shell command.** It is interpolated inside
plugin manifests (`.mcp.json`) but is *not* exported to the shell, so
it expands to an empty string and `python3 "/skills/…/validate_okf.py"` fails with
"No such file or directory". If you genuinely do not know the absolute path, ask the
user for it rather than guessing.

## If the MCP tools are present, read through them

This plugin registers its own MCP server in `.mcp.json`, so **in any session with the
plugin loaded these tools already exist** — namespaced, as `mcp__okf__okf_map`,
`mcp__okf__okf_get`, `mcp__okf__okf_neighbours`, `mcp__okf__okf_search`,
`mcp__okf__okf_validate`. Check for them before reaching for a script path or reading
a pile of files. Nothing needs launching; the server is already running.

| Instead of | Call |
|------------|------|
| Reading `index.md` then hunting through notes | `okf_map` once — every note's path, type, description, trust flags and outbound links in one payload |
| Grepping for what references a note | `okf_neighbours` with `direction: "in"` — backlinks, which grep answers only expensively and a file read not at all |
| Shelling out to `validate_okf.py` | `okf_validate` |
| Reading notes one at a time | `okf_get` with **every** path you need in one call |

**The MCP is read-only, so authoring still goes through the filesystem.** Creating
notes, editing frontmatter, updating `index.md` and `log.md` — all Write/Edit against
the vault directory as normal. The division is: **read through the MCP, write through
the filesystem.** After writing, `okf_validate` or `okf_get` confirms what landed —
the server rescans changed files by itself, so there is nothing to restart or refresh.

**If a tool answers "no vaults are configured"**, falling back to Read/Grep on the
vault directory is the right way to get the work done — the MCP is an optimisation,
not the only route. But **say so once, naming the cause and the fix**, rather than
mentioning it in passing and moving on. Left unsaid, the vault stays unregistered and
every later session pays the same cost: no map, no backlinks, more turns.

The server looks in three places, so exactly one of these is true:

- **Nothing to find.** No `.claude/okf.json` at or above the project, and no
  directory holding both `index.md` and `log.md` at the project root or one level
  below it. Auto-detection covers the ordinary layouts, so this usually means the
  vault is nested deeper — offer to add a `"vault"` field to `.claude/okf.json`,
  which takes effect **without a restart**.
- **`enabled: false`** in the config, which the server treats as a decision and will
  not overrule by detection.
- **An explicit `--vault` that did not resolve** to a directory. It never silently
  falls back, by design.

Report which one, in a line, then carry on with the filesystem.

## Workflows

### Scaffold a new vault

1. Confirm the vault's purpose and root directory with the user.
2. Create the root **`index.md`** from `assets/templates/index.md`: state what the
   vault is (name the format and link the OKF spec), how it is organised, and a
   suggested reading order. Declare the version in its frontmatter
   (`okf_version: "0.2"`) — the root index is the only place a bundle declares it,
   and the only `index.md` that carries frontmatter.
3. Create **`log.md`** from `assets/templates/log.md` with a first dated entry
   (absolute date) recording vault creation.
4. Create the initial folder hierarchy; give **every folder its own `index.md`**.
5. Run the validator (below) and confirm zero hard failures.

### Add or edit a concept note

1. Choose the folder and a stable file path — the **path is the identity**.
2. Copy `assets/templates/concept.md` and fill the frontmatter:
   - `type` — required, non-empty, meaningful, consistent with the vault's existing
     types.
   - `title` and `description` — always both; `description` is a genuine one-line
     recall aid an agent uses to judge relevance, **not** a restatement of the title.
   - `tags`; `resource` (URL or bundle-relative path) where applicable.
   - `generated: { by, at }` — the actor and ISO-8601 time the content was produced
     (`generated.at` supersedes the v0.1 `timestamp`). Add `verified`, `status`,
     `stale_after`, and `sources` where trust/provenance/lifecycle matter (all
     optional; see `references/conventions.md` and `okf-spec.md`).
   - Add project-specific custom fields only where they aid the consuming project.
3. Body: lead with a one-line orientation, use conventional `##` sections, cite
   sources via the `sources` frontmatter (footnotes keyed to a source `id`), and
   **link liberally** to related concept notes — each link is a graph edge.
4. Wire it in on both axes: link to it from the relevant folder `index.md` (for
   discovery — so it is not *unreachable*) **and** from any genuinely related concept
   notes (so it is not *unreferenced* — an index listing alone does not count as a
   knowledge reference).
5. Record the change in `log.md` and re-run the validator.

### Add a view (index, matrix, roll-up)

Views are notes, not duplication. Create a note with a descriptive `type` (e.g.
`Comparison Matrix`) that **links to** the underlying concept notes rather than
copying their content. The concept note stays the source of truth; the view is a
projection. See the matrix pattern in `references/conventions.md` §2.

### Maintain (rename, split, delete)

On any structural change: **repoint every reference**, re-run the validator to catch
missed links, and record the change in `log.md` with an absolute date.

### Convert loose notes into OKF

1. Identify concepts; make **one file per concept** at a stable path.
2. Add frontmatter (at minimum a meaningful `type`) to each.
3. Turn implicit relationships into Markdown links between the files.
4. Create root `index.md` and `log.md`; add per-folder `index.md`.
5. Run the validator and resolve hard failures; treat link/connectivity warnings as
   a cleanup backlog.

### Migrate a v0.1 vault to v0.2

v0.2 is backward-compatible: a v0.1 vault stays valid untouched (legacy `timestamp`
and body `# Citations` are still accepted). So migrate for idiomatic cleanliness,
not correctness, and do it with judgement — there is deliberately no migration
script. Run the validator first; its report is the migration checklist.

- **Safe bulk edit:** add `okf_version: "0.2"` to the **root** `index.md` frontmatter.
- **Do not fabricate provenance.** Never bulk-fill `generated.by`/`verified` across
  historical notes — that manufactures trust signals no one actually produced or
  reviewed, corrupting the very thing the fields exist for. Leave legacy `timestamp`
  in place (it validates); add `generated`/`verified` **truthfully, going forward**,
  as notes are genuinely edited and confirmed.
- **Citations, per note:** where a note carries a body `# Citations`/`# Sources`
  list, lift it into structured `sources` frontmatter (each with a `resource`, and
  an `id` if the body cites it) — a judgement call best done note by note.
- **Reserved-name collisions are a human decision, not an auto-fix.** If a vault
  already uses a field name v0.2 now reserves — most commonly `status` (v0.2 enum:
  `draft|stable|deprecated`) — do **not** silently rewrite the project's values.
  Surface the collision and let the owner choose: rename the project field (e.g.
  `lifecycle_state`) or adopt the v0.2 semantics. The skill supplies no project
  vocabulary and must not overwrite it.

### Visualise the vault

To *see* a vault's shape rather than read it as Markdown, render it as an
interactive graph:

```bash
python3 "<skill-dir>/scripts/graph_server.py" <vault-dir> --no-reserved
```

It parses the vault, serves a self-contained page on a local port, and opens a
browser. Nodes are sized by concept-degree (hubs stand out); an outer ring shows the
v0.2 trust tier; isolated notes render as hollow rings; clicking a node shows its
frontmatter, trust/provenance, and links. Add `--query <text>` to focus on matching
notes and their neighbours; keep `--no-reserved` to exclude index/log navigation
nodes from the concept graph. Launch it in the background (it serves until stopped)
and give the user the printed URL. The server **watches the vault and pushes updates
to the open page over Server-Sent Events**, merging them into the running layout —
so edits appear live, no restart. Stdlib-only — the only runtime is a transient
local HTTP server, so it stays within OKF's no-dependencies stance.

### Serve a vault to a remote or API-based model (MCP)

A model reached over an API cannot walk a directory, so it needs an interface. The
skill bundles a **read-only MCP server** over stdio for that:

```bash
python3 "<skill-dir>/scripts/okf_mcp.py" \
  --vault [name=]<vault-dir> [--vault name=<other-vault> …]
```

It speaks newline-delimited JSON-RPC on stdin/stdout, so whichever process runs the
tool loop launches it as a subprocess: the **model** is remote, the server is not.
Nothing is hosted and nothing is authenticated — that stays true only while the
client is one the vault's owner runs.

Discovery, in precedence order: an explicit `--vault`; then the `vault` field of
`.claude/okf.json`, searched for at `$CLAUDE_PROJECT_DIR` and the working
directory and then upward to `$HOME`; then **auto-detection** of any directory holding
both `index.md` and `log.md` at a project root or one level below it. OKF's reserved
filenames make a bundle self-identifying, so an ordinary project needs no
configuration at all — `--no-autodetect` turns that off. A config file that exists is
authoritative, `enabled: false` included: detection fills a silence, it does not
overrule a decision.

All of it is **live** — creating a vault or writing the config mid-session takes
effect without restarting the server. Passing `--vault` opts out
entirely: an explicit vault is never overridden, and never silently falls back if it
fails to resolve.

Five tools — `okf_map`, `okf_get`, `okf_neighbours`, `okf_search`, `okf_validate` —
plus three resources per vault (`okf://<name>/_map`, `_index`, `_vocab`) and an
`okf://{vault}/{path}` template for individual notes. Path-as-identity means a note's
resource URI *is* its identifier.

**The design goal is one round trip**, and getting it depends on how the client is
set up: attach the `_map` resource to the context **before** the first turn, and the
model's opening move already knows every note's path, type, description, trust flags
and outbound links — so it can go straight to a single batched `okf_get`. Left as a
tool call instead, orientation costs a turn. Where the client supports prompt
caching, cache the map: it changes only when the vault does.

To see the map (and what it costs) without a client in the loop:

```bash
python3 "<skill-dir>/scripts/okf_map.py" <vault-dir>
```

It prints the map on stdout and an approximate token count on stderr. Budget roughly
**57 tokens per note** with outbound links, ~35 without; past `--max-notes` (default
400, ≈23k tokens) the lowest-degree notes keep their descriptions but lose their link
lines, and the map says so rather than truncating silently. A vault of a few thousand
notes should not be mapped whole — point the model at `_vocab` and `okf_search`
instead.

When advising on which interface to use: a vault in a git repo is already readable by
any client with repository access, so the MCP earns its place for what a file read
cannot give — backlinks, multi-hop neighbourhoods, facet filters, and the map itself.

## Validation

Run the bundled stdlib validator (no dependencies) against a vault directory,
resolving `<skill-dir>` as described in "Running the bundled scripts" above. Where the
vault is served over this plugin's MCP server, call `okf_validate` instead — same
report, no path to resolve:

```bash
python3 "<skill-dir>/scripts/validate_okf.py" <vault-dir>
```

It checks frontmatter validity, link integrity, connectivity (which notes are
*unreferenced* vs *unreachable*), the v0.2 trust/provenance/lifecycle signals, and
flags hub outliers with their removal impact. The printed report is self-describing
— read it rather than relying on an enumeration here (the checks evolve with the
script).

Exit codes align with OKF's tolerance of broken links: **only a missing/empty `type`
(or a malformed frontmatter block) is a hard failure** (exit 1). Broken links and
connectivity gaps are warnings — the validator *reports*, it does not hard-fail authors. Use
`--strict-links` to also gate on broken links (e.g. in CI a project chooses to be
strict), and `--quiet` for summary counts only.

Guidance stance: **guide, do not enforce.** Surface issues from the report and fix
them by repointing links or completing frontmatter; do not rewrite an author's
choices to satisfy the linter.

## Additional resources

- **`references/okf-spec.md`** — distilled OKF v0.2 essentials (trust/provenance/
  lifecycle fields, actor convention, `okf_version`, the v0.1→v0.2 renames), pinned
  to spec version, with the primary source link and what OKF deliberately is not.
- **`references/conventions.md`** — the authoring conventions with good/bad
  examples, the view/matrix pattern, and *when NOT to use OKF* (reach for a typed
  graph instead).
- **`assets/templates/`** — `concept.md`, `index.md`, `log.md` starting points.
- **`scripts/okf_graph.py`** — the shared vault parser and graph model. Every script
  below imports it, so the validator, the viewer and the MCP server cannot disagree
  about what a vault contains.
- **`scripts/validate_okf.py`** — the integrity validator.
- **`scripts/graph_server.py`** — the interactive graph viewer (see "Visualise the
  vault"); launched via the skill, not a standalone command.
- **`scripts/okf_map.py`** — the whole-vault map builder, usable as a CLI.
- **`scripts/okf_mcp.py`** — the read-only stdio MCP server (see "Serve a vault to a
  remote or API-based model").
