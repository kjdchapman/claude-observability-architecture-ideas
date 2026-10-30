---
type: Design Question
title: Shape of a good outcome
description: Wanted output is a clear problem statement plus several options, each with a sketched target architecture, compared on pros, cons and heuristics, with the reasoning made explicit.
tags: [observability, design-tree, outcome]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T16:30:00Z }
status: draft
exploration: explored
---

# Shape of a good outcome

Branch of the [observability architecture exploration](/exploration/observability-architecture.md):
what "done" looks like for this exploration.

## Understanding

The team has **little insight into this problem space yet**. The goal is to learn what the
options are and how to choose between them, not to pick one immediately.

The prototyping should produce:

1. **A pinned-down problem statement**, grounded in the
   [401 cache poisoning incident](/incidents/third-party-401-cache-poisoning.md) and the
   gaps found so far.
2. **Several options**, each with a **sketched target architecture**.
3. **A comparison of the options**: pros and cons, and the **heuristics** for when each
   option fits.
4. Options that **mitigate** the problem as well as options that **solve** it.
5. **Reasoning shown throughout**: each judgement says why it was made, so the team can
   check it and reuse it.

Options must respect the [constraints](/exploration/constraints.md): AWS as the platform,
procurement for outside tools, and cost.

## Assumptions surfaced

- The primary audience is the team itself, building its own understanding. Not confirmed:
  the output may also need to convince someone else, such as procurement.

## Questions this opened

- [Mitigate or solve](/exploration/mitigate-vs-solve.md): what separates a mitigation from a solution here.
