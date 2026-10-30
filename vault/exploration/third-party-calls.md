---
type: Design Question
title: Dependency call visibility
description: Should calls to external dependencies such as the third-party data provider be first-class telemetry (status, latency and auth outcome per caller), and how much should the architecture invest in it?
tags: [observability, design-tree, third-party, dependencies]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T18:00:00Z }
status: draft
exploration: unexplored
---

# Dependency call visibility

Opened by [Motivation](/exploration/motivation.md). The
[incident](/incidents/third-party-401-cache-poisoning.md) began with a failing call to an
external dependency. Reframed on 2026-10-30 from "how are third-party calls seen today"
into an architecture question: what the target design should show about outbound
dependencies.

## Understanding

Not yet explored.
