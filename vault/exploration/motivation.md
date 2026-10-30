---
type: Design Question
title: Motivation
description: Driven by a third-party 401 incident in which one shared-cache failure hit every ECS task but only one task logged the cause, so tracing the origin took a long time.
tags: [observability, design-tree, motivation]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T15:20:00Z }
status: draft
exploration: explored
---

# Motivation

Branch of the [observability architecture exploration](/exploration/observability-architecture.md):
the problem or gap behind the exploration.

## Understanding

The trigger was a real incident:
[third-party 401 cache poisoning](/incidents/third-party-401-cache-poisoning.md). The
question the team could not answer quickly was **"where did the first error come from?"**
The symptom, errors served from a shared cache, appeared on every ECS task. The cause,
one failing call during a cache refresh, was logged once, on a single task.

So the core gap is **following an effect back to its originating event across
instances**, when shared state carries the failure from one place to many.

## Questions this opened

- [Where the originating log lived](/exploration/log-location.md): were logs centralised, or per task?
- [Shared cache provenance](/exploration/cache-provenance.md): which task wrote a cache entry, from which call, and when?
- [Third-party call visibility](/exploration/third-party-calls.md): how outbound calls, and their auth outcome, are seen per call site.
- [Detection](/exploration/detection.md): how the incident was noticed, and how quickly.
