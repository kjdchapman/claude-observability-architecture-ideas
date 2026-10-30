---
type: Design Question
title: Refresh trigger
description: What triggers a shared-cache refresh (a request that finds an expired entry, a timer inside a task, a scheduled job), and does it run in a request-serving ECS service?
tags: [observability, design-tree, cache, ecs]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:25:00Z }
status: draft
exploration: deferred
---

# Refresh trigger

Opened by [Service topology](/exploration/service-topology.md). In the
[401 incident](/incidents/third-party-401-cache-poisoning.md), the failing call ran only on
refresh. What triggers a refresh decides when the failure can happen and which signals
would show it. Related: [cache recovery](/exploration/cache-recovery.md),
[release verification](/exploration/release-verification.md).

## Understanding

Not yet explored.

## Deferred

Out of scope as of 2026-10-30: this asks about diagnosing the incident, not about designing the observability architecture.
