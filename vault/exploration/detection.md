---
type: Design Question
title: Detection
description: The 401 incident was spotted only because the team was watching after a release; incidents are usually found through user reports, which the team calls a massive issue.
tags: [observability, design-tree, alerting, detection]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:15:00Z }
status: draft
exploration: explored
---

# Detection

Opened by [Motivation](/exploration/motivation.md), from the
[incident](/incidents/third-party-401-cache-poisoning.md).

## Understanding

- The 401 incident was noticed because the team was **looking after a release**. The alerts
  didn't fire ([details](/exploration/audience-and-use.md)).
- **Usually, incidents are found through user reports.** The team calls this a
  **massive issue**.
- How long it takes to notice is **not measured**. Without watching after a release, this
  incident would probably have waited for a user to report it.

## Assumptions surfaced

- Detection relies on people: someone watching after a release, or a user complaining.
  None of it is automated, which makes this one of the biggest gaps found so far.

## Questions this opened

- [Release verification](/exploration/release-verification.md): what gets checked after a release, by whom, and for how long.
- What should fire instead is covered by [alert design](/exploration/alert-design.md).
