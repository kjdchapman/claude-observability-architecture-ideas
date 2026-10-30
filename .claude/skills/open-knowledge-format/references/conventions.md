# OKF authoring conventions

The proven conventions that make an OKF vault navigable and agent-consumable —
extracted from a working vault, not authored speculatively from the spec. These
are the value above the one-page format: apply them so two different sessions
produce structurally consistent vaults.

These conventions are **format-generic**. They carry no project, customer, or
domain vocabulary. Any fixed `type` enum, or fields like `category` /
`blueprint_entity` / `status`, belong to the *consuming project*, not here.

---

## 1. Concept notes

**One concept per file; the path is the identity.** Never split a single concept
across files or bundle many concepts into one file.

### Frontmatter discipline

- **`type`** — required, non-empty, and *meaningful*. Use it as the routing/
  filtering axis for the vault (e.g. `Vendor`, `Constraint`, `Persona`,
  `Comparison Matrix`, `Analysis`). Keep the set of types small and consistent
  within a vault.
- **`title` and `description`** — always include both.
  - `description` is a **genuine one-line recall aid** — the sentence an agent
    reads to decide whether this note is relevant. It must add information, not
    restate the title.
    - Bad: `title: EU AI Act` / `description: The EU AI Act.`
    - Good: `description: HR/employment AI is Annex III high-risk; obligations apply from 2 Aug 2026.`
- **`tags`** — a YAML list, e.g. `[constraint, eu-ai-act, high-risk]`. Lower-case,
  hyphenated, reused across notes.
- **`generated`** — `{ by: <actor>, at: <ISO 8601> }`. Records how the current
  content was produced and when it last meaningfully changed. **`generated.at`
  supersedes the v0.1 `timestamp` field** — prefer it; a bare `timestamp` still
  validates as a legacy fallback.
- **`resource`** — the canonical identifier of the underlying asset: an absolute
  URL, a bundle-relative `/path`, or a `references/…` path. Omit for abstract
  concepts.
- **Custom fields** are allowed and encouraged where they aid the consuming
  project — but supply none by default. Add them at the point of use.

### Trust & lifecycle signals (v0.2, optional)

All optional, but worth setting in an agent-maintained corpus — their *absence* is
itself a signal (an unverified concept is distinguishable, never rejected):

- **`generated.by` / `verified`** drive a consumer-derived **trust tier**: no
  `verified` → *unverified*; verified only by `process:`/tool actors →
  *machine-confirmed*; verified by any `human:<id>` → *human-reviewed*. Use the
  **actor convention** so tiers work: `human:<id>`, `process:<id>`,
  `<producer>/<version>`.
- **`status`** — `draft | stable | deprecated` (absent ⇒ `stable`). Deprecate
  rather than delete when a concept is superseded but worth keeping.
- **`stale_after`** — `YYYY-MM-DD`; the concept wants re-verification once reached.

### Body

- Lead with a **one-line orientation**: what the concept is and why it is in the
  vault.
- Use conventional `##` sections where they fit (e.g. `# Schema`, `# Examples`).
- **Cite sources via the `sources` frontmatter**, not a body list. Give each source
  a stable `id` and reference it inline with a Markdown footnote (e.g.
  `…per the schema[^ga4-schema]`). This replaces the v0.1 `# Citations` body list;
  a legacy `# Citations`/`# Sources` section still parses but is no longer preferred.
- Link liberally to related concept notes inline — every link is a graph edge.

---

## 2. Structure & views

**Concepts are files; views are notes.** A comparison table, category roll-up, or
matrix is *its own note* that **links to** the underlying concept notes rather
than duplicating their content. Give a view a descriptive `type` (e.g.
`Comparison Matrix`) and have it link out to every concept it summarises.

- The source of truth is the concept note. A view referencing it via a frontmatter
  axis (e.g. a vendor's `category`) and a link is a *projection*, never a copy.
- Use folders for **coarse hierarchy**, but remember the real structure is the
  **link graph, not the directory tree**. Do not over-nest.
- **Every folder gets an `index.md`** so a human or agent entering the folder can
  navigate onward (progressive disclosure).

### The view/matrix pattern (from a working vault)

A matrix note leads with a one-line orientation and a legend, then a table whose
first column links to each concept. The names and columns below are **illustrative**
(taken from one working vault) — the pattern is generic; the vocabulary is not:

```markdown
| Vendor | Open API | Native AI | Tier |
|---|---|---|---|
| **[Pinpoint](/vendors/pinpoint.md)** *(incumbent)* | ●●● | ●●○ | 🟡 |
| [Ashby](/vendors/ashby.md) | ●●● GraphQL | ●●● | 🟢 |
```

The detail lives in `pinpoint.md` and `ashby.md`; the matrix only *projects and
links*.

---

## 3. Reserved files

### Root `index.md`

States **what the vault is** (name the format + link the OKF spec), **how it is
organised** (each top-level folder, linked to its sub-index), and a **suggested
reading order**. A human unfamiliar with the vault must be able to orient from the
root `index.md` alone. Close with a link to `log.md`. The root `index.md` is the one
place a bundle declares its version — a small frontmatter block with
`okf_version: "0.2"` (folder-level `index.md` files carry no frontmatter).

### `log.md`

Append-only chronological history, **newest first**. Every material change gets a
dated entry under a `## YYYY-MM-DD` heading. **Convert relative dates to absolute.**
Record structural changes especially — notes added, renamed, split, deleted, and
references repointed.

---

## 4. Linking

- Relationships are Markdown links to concept files. **Prefer stable, path-based
  links** rooted at the vault (`/folder/concept.md`) — the working vault uses
  absolute-from-root links throughout, which survive folder-relative moves better
  than `../` chains.
- Anchors (`/folder/concept.md#section`) are fine and the validator strips them
  before resolving.
- Link liberally: a link is a graph edge, and richer linking makes the vault more
  navigable and more useful to agents.

---

## 5. Maintenance

On any structural change (rename, split, delete):

1. **Repoint every reference** to the moved/renamed/deleted concept.
2. **Re-run the validator** (`scripts/validate_okf.py`) to catch links the repoint
   missed.
3. **Record the change in `log.md`** with an absolute date.

---

## When NOT to use OKF

Recommend a different substrate — and say so plainly — when the knowledge has
outgrown exploration:

- **Relationships need to be typed and queried.** OKF edges are untyped links;
  if the work needs "all X that depend on Y of type Z", a typed model (GraphQL /
  Blueprint-style entities, a graph database) fits better.
- **Schema must be enforced.** OKF fixes no field schema beyond a non-empty
  `type`; if invalid records must be rejected at write time, use a typed store.
- **Concurrent structured writes / transactions** are required.

OKF is the low-ceremony, portable, exploratory tier. Naming its limits earns
trust and keeps the vault from being pushed past what it is good at. Do not turn
a one-page format into a heavyweight framework.
