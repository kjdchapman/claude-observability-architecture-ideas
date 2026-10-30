# OKF v0.2 — distilled essentials

**Pinned to:** OKF v0.2 (Google Cloud, `GoogleCloudPlatform/knowledge-catalog`).
**Primary source:** <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>
**v0.2 announcement:** <https://cloud.google.com/blog/products/data-analytics/okf-v0-2-adds-trust-signals>

OKF is young and may churn. This file is the extracted essentials, not a substitute
for the source. If behaviour here conflicts with a newer published spec, the
published spec wins — flag the drift.

## What OKF is

A vendor-neutral open specification for representing curated knowledge as a
**directory of plain Markdown files with YAML frontmatter**, where relationships
are ordinary Markdown links. Readable by a human with `cat`, by any Markdown tool,
and by an LLM verbatim, in any git repo with no runtime, SDK, or server. No schema
registry, no central authority, no required tooling.

## The five rules that constrain every vault (unchanged since v0.1)

The five operating rules are stated tersely in `SKILL.md`: directory of Markdown
files; file path = concept identity; required non-empty `type`; reserved
`index.md`/`log.md`; links are directed, untyped edges (broken links tolerated).

## Frontmatter fields

**Required:** `type` — a producer-defined string for routing/filtering/presentation.
The only always-required key. Not centrally registered.

**Recommended:** `title`, `description` (single sentence), `resource` (an absolute
URL **or** a bundle-relative `/path` **or** a `references/…` path — absent for
abstract concepts), `tags` (YAML list). Producers may add any custom keys; consumers
must preserve unknown keys when round-tripping.

## What v0.2 adds: provenance, trust, lifecycle

All of the following are **optional** and **backward-compatible**. Their *absence*
carries meaning (an unverified concept is distinguishable but never rejected).

### Provenance — `sources`

A list; each entry describes material the concept draws on:

```yaml
sources:
  - id: ga4-schema                 # optional stable key for footnote citations
    resource: https://…            # REQUIRED per entry: URL, /bundle/path, or references/…
    title: GA4 BigQuery Export schema
    author: team:ga4-docs          # credibility signal (actor convention)
    usage_count: 5000              # liveness/adoption signal
    last_modified: 2026-05-30      # YYYY-MM-DD, when the source itself last changed
usage_window: { from: 2026-06-01, to: 2026-06-30 }   # frames usage_count values
```

Body claims cite a source with a Markdown footnote keyed to its `id`. This
**supersedes the v0.1 body `# Citations` list**.

### Trust — `generated` and `verified`

```yaml
generated: { by: reference_agent/gemini-2.5-pro, at: 2026-06-20T22:53:05Z }
verified:
  - { by: human:ahormati, at: 2026-06-25T09:00:00Z }
  - { by: process:finance-nightly, at: 2026-06-26T02:00:00Z }
```

- `generated.by` (required if `generated` present) — the actor that produced the
  current content. `generated.at` (optional) — ISO 8601 of last meaningful change.
  **`generated.at` supersedes the v0.1 `timestamp` field.**
- `verified` — a list of confirmation events (`by` actor, `at` ISO 8601). A single
  verifier may be a bare mapping; consumers treat it as a one-element list.
- **Trust tier** (derived by consumers, not stored): no `verified` → *unverified*;
  `verified` by non-`human:` actors only → *machine-confirmed*; any `human:<id>`
  verifier → *human-reviewed*. Advisory signal for filtering, not access control.

### Lifecycle — `status` and `stale_after`

```yaml
status: stable          # draft | stable | deprecated (absent ⇒ stable)
stale_after: 2026-09-23 # YYYY-MM-DD; concept is stale once today ≥ this date
```

### Actor convention

Identity fields (`generated.by`, `verified[].by`, `sources[].author`) use:
`<producer>/<version>` (agents/tools, e.g. `reference_agent/gemini-2.5-pro`),
`human:<id>` (people), `process:<id>` (automated processes), or another
`<role>:<id>` prefix such as `team:<id>` for group authorship (common in
`sources[].author`, e.g. `team:ga4-docs`). Consumers key trust specifically off the
`human:` prefix, so hand-authored/confirmed content **must** use it.

### Attested Computation (new concept type)

A `type: Attested Computation` note carries both what a value means and a sanctioned
way to compute it (`runtime`, `parameters`, `computation`, `executor`, `attester`),
so a consumer can confirm the blessed computation ran rather than an improvised one.
The skill does not author these by default; treat as an advanced, opt-in pattern.

## Reserved files & versioning

- `index.md` — progressive-disclosure directory listing at any level. Carries **no
  frontmatter except** an optional `okf_version` at the **bundle root**:
  ```yaml
  ---
  okf_version: "0.2"
  ---
  ```
  Consumers that don't understand the declared version attempt best-effort
  consumption rather than refusing the bundle.
- `log.md` — chronological history, date-grouped **newest first**, ISO `YYYY-MM-DD`
  headings.

## Backward compatibility (v0.1 → v0.2)

v0.2 is a minor, additive bump. v0.1 bundles remain consumable. Two renames:

1. `timestamp` → `generated.at`. Consumers **may** fall back to a legacy `timestamp`
   when `generated` is absent.
2. body `# Citations` list → `sources` frontmatter. Consumers **should** read
   `sources` and **may** still parse a legacy `# Citations` body list.

## Consequences for tooling

The format tolerates broken links and fixes no field schema beyond a non-empty
`type`, so tooling should **report rather than enforce**. The bundled
`scripts/validate_okf.py` treats only a missing/empty `type` (or a malformed
frontmatter block) as a hard failure; everything else — broken links, orphans,
missing recommended fields, malformed v0.2 signals — is a warning. Its docstring
carries the exit-code contract.
