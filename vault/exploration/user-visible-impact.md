---
type: Design Question
title: User-visible impact
description: If the poisoned cache affected every ECS task but the app looked healthy, what did users actually see (errors, missing data, stale data), and in which product?
tags: [observability, design-tree, client-side, impact]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:50:00Z }
status: draft
exploration: deferred
---

# User-visible impact

Opened by [Firebase and client-side signals](/exploration/client-side-signals.md). The
[401 incident](/incidents/third-party-401-cache-poisoning.md) put an error into the shared
cache, yet the app looked healthy when checked. What a failure looks like to users decides
which signals and [alerts](/exploration/alert-design.md) could catch it.

## Understanding

Not yet explored.

## Deferred

Out of scope as of 2026-10-30: this asks about diagnosing the incident, not about designing the observability architecture.
