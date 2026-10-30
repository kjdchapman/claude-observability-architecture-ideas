---
type: <REQUIRED — meaningful producer-defined string, e.g. Vendor, Constraint, Persona, Comparison Matrix>
title: <human-readable title>
description: <one-line recall aid an agent uses to judge relevance — NOT a restatement of the title>
tags: [<tag>, <tag>]
resource: <canonical URL, /bundle/path, or references/… if this note is about a concrete asset — omit for abstract concepts>
# --- provenance (v0.2, optional; supersedes the v0.1 "# Citations" body list) ---
sources:
  - id: <stable-key, referenced by a body footnote>
    resource: <URL, /bundle/path.md, or references/… — REQUIRED per source>
    title: <human-readable label>
    author: <team:… | human:… | process:… | producer/version>
    last_modified: <YYYY-MM-DD>
# --- trust (v0.2, optional; generated.at supersedes the v0.1 "timestamp" field) ---
generated: { by: <producer/version | human:id | process:id>, at: <ISO 8601, e.g. 2026-07-27T00:00:00Z> }
verified:
  - { by: <human:id | process:id>, at: <ISO 8601> }
# --- lifecycle (v0.2, optional) ---
status: <draft | stable | deprecated>    # absent ⇒ stable
stale_after: <YYYY-MM-DD>                # concept is stale once today ≥ this date
# Custom fields are allowed and encouraged where they aid the consuming project.
# Delete any optional lines above that this note does not need.
---

# <title>

<One-line orientation: what this concept is and why it is in the vault.>

## <Section>

<Body. Use conventional sections where they fit — e.g. Schema, Examples.
Link liberally to related concept notes: a link is a graph edge, e.g.
[Related concept](/folder/related-concept.md).
Cite a source inline with a footnote keyed to its `sources` id, e.g.
…as documented in the export schema[^ga4-schema].>

[^ga4-schema]: the `sources` entry with `id: ga4-schema`.
