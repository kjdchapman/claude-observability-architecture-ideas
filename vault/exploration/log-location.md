---
type: Design Question
title: Where the originating log lived
description: Logs were already centralised and searchable; the gap was correlation, made worse by two teams sharing one web server but each looking only at its own product.
tags: [observability, design-tree, logging, ecs]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T15:35:00Z }
status: draft
exploration: explored
---

# Where the originating log lived

Opened by [Motivation](/exploration/motivation.md), from the
[incident](/incidents/third-party-401-cache-poisoning.md).

## Understanding

**Correlation, not aggregation.** Logs from all ECS tasks were in one searchable place.
The originating line was findable in principle, but nothing linked it to the 401s seen
everywhere else.

A human factor made it worse. **Two applications, an app and a website, run on the same
web server**, and **separate teams** own them. Each team tends to watch only its own
product. Searching across both products in the shared log store is possible in principle,
but no combined view is known to have been set up
([existing tooling](/exploration/existing-tooling.md)).

## Constraints and assumptions

- Centralised log search already exists, so an architecture can assume it, not build it.
- Better tools alone may not help if teams keep looking at one product at a time.
- Corrected 2026-10-30: an earlier version said combined views "exist but aren't the
  habit". The team isn't aware of any.

## Questions this opened

- [Team silos](/exploration/team-silos.md): how ownership boundaries shaped the investigation.
- [Shared platform](/exploration/shared-platform.md): exactly what the app and website share.
