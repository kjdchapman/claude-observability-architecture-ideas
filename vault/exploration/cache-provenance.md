---
type: Design Question
title: Shared cache provenance
description: The shared cache is ElastiCache running Valkey; no one knows what the failed refresh wrote, though it looked like a cached error, so nothing records what was cached or who wrote it.
tags: [observability, design-tree, cache, elasticache, valkey]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:00:00Z }
status: draft
exploration: explored
---

# Shared cache provenance

Opened by [Motivation](/exploration/motivation.md). In the
[incident](/incidents/third-party-401-cache-poisoning.md), shared state carried a failure
from one task to all of them.

## Understanding

- The shared cache is **Amazon ElastiCache running Valkey**.
- **No one knows what was written** to the cache when the refresh got the 401. It
  **looked like a cached error**, but that is an inference, not something observed.
- So after the event, nothing showed **what** went into the cache, **which task** wrote it,
  or **when**. Even after the incident, the cache's contents and history can't be checked.

## Assumptions surfaced

- Treated as likely but unconfirmed: the refresh path stores whatever comes back, so an
  error response can be cached as if it were data.

## Questions this opened

- [Cache recovery](/exploration/cache-recovery.md): how the poisoned entry was cleared, and what the TTL is.
