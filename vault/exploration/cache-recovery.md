---
type: Design Question
title: Cache recovery
description: How was the poisoned Valkey entry cleared (flush, waiting for its TTL, a redeploy), how long were users affected, and would a shorter TTL or refusing to cache errors have limited the damage?
tags: [observability, design-tree, cache, valkey, recovery]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:00:00Z }
status: draft
exploration: deferred
---

# Cache recovery

Opened by [Shared cache provenance](/exploration/cache-provenance.md). How a poisoned entry
is cleared, and how long it lasts, sets how long an incident like the
[401 cache poisoning](/incidents/third-party-401-cache-poisoning.md) lasts. Related:
[mitigate or solve](/exploration/mitigate-vs-solve.md).

## Understanding

Not yet explored.

## Deferred

Out of scope as of 2026-10-30: this asks about diagnosing the incident, not about designing the observability architecture.
