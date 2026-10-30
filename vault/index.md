---
okf_version: "0.2"
---
# Observability architecture ideas

An [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
(OKF v0.2) vault: plain Markdown files with YAML frontmatter, where relationships are Markdown links.

## Purpose

A prototyping space for exploring options for an observability architecture for our
AWS-hosted services. Nothing here is a commitment: notes are `status: draft` unless
marked otherwise, and record ideas, trade-offs and open questions rather than decisions.

## How this vault is organised

- **[Exploration](/exploration/index.md)**: the design tree from structured questioning
  sessions. One note per question; each links to its parent and to the questions it opened.
  The custom `exploration` field tracks progress: `unexplored`, `exploring`, `explored`, or
  `deferred` (judged out of scope).
- **[Incidents](/incidents/index.md)**: real incidents that motivate the exploration.
- **[Decisions](/decisions/index.md)**: architecture decision records setting out options and reasoning.

## Reading order

1. [Session summary, 2026-10-30](/exploration/summary-2026-10-30.md): the problem, constraints, desired outcome and open questions so far.
2. [ADR-001](/decisions/adr-001-observability-architecture.md): the options and how they compare.
3. [Observability architecture exploration](/exploration/observability-architecture.md): the root of the design tree.
4. Follow its links into each branch.

See [log](/log.md) for change history.
