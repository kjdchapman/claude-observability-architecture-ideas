---
type: Design Question
title: Shared platform
description: Shared AWS components are jointly owned but effectively unowned; the web team knows the infrastructure better because AWS is its whole estate, while the app team is seen as app-centric.
tags: [observability, design-tree, aws, ecs, ownership]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T16:50:00Z }
status: draft
exploration: explored
---

# Shared platform

Opened by [Where the originating log lived](/exploration/log-location.md). Overlaps with
[current estate](/exploration/current-estate.md) and with
[team silos](/exploration/team-silos.md).

## Understanding

- Shared pieces (the cache, third-party client code, and the CloudFront and ECS setup) are
  **jointly owned** by the app and website teams.
- **In practice no one owns them.** Jointly owned components get no single owner, and
  there is a slight problem with silos and with knowledge not crossing between teams.
- The **app team is seen as app-centric**: it has other components of its own outside AWS
  (see [Firebase and client-side signals](/exploration/client-side-signals.md)).
- The **web team knows the infrastructure better**, because the AWS-hosted components are
  its whole estate.

## Assumptions surfaced

- Knowledge of the shared infrastructure is uneven, so an option that only one team can
  run or interpret would make the silo deeper, not shallower.

## Questions this opened

- [Operating ownership](/exploration/operating-ownership.md): who would own and run whatever observability is built.
