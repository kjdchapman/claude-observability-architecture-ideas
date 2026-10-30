---
type: Design Question
title: Alert design
description: Wants a mix of symptom-based and cause-based alerting, with the reasoning for each explained, aiming to hear about issues before a callout and well before users get a poor experience.
tags: [observability, design-tree, alerting, slack]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T18:15:00Z }
status: draft
exploration: explored
---

# Alert design

Opened by [Audience and use](/exploration/audience-and-use.md). The existing alerts (CPU
and load balancer latency) missed the
[401 cache poisoning incident](/incidents/third-party-401-cache-poisoning.md). Related:
[detection](/exploration/detection.md) and
[existing tooling](/exploration/existing-tooling.md).

## Understanding

- The team wants **a mix of both**:
  - **symptom-based** alerts: users are affected, for example by user-facing error rates or failing key-page checks
  - **cause-based** alerts: a component is failing, for example a dependency or the cache
- It wants to **understand why** you would pick each one. The options comparison should
  explain the reasoning, not just recommend
  ([shape of a good outcome](/exploration/good-outcome.md)).
- Goals, in order of how early they want to know:
  1. Ideally, **before it results in a callout**.
  2. Definitely **before users get a poor experience**.
  3. Before **the web presence looks bad** (a reputational concern).

## Assumptions surfaced

- Hearing about problems before users do means relying on **leading indicators**, such as
  rising dependency errors or failed refreshes. Symptom-based alerts alone only fire once
  users are already affected.

## Questions this opened

- [What a callout means](/exploration/callout-meaning.md): what the team means by "callout", which sets the earliest warning point.
