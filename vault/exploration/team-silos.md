---
type: Design Question
title: Team silos
description: Both teams investigated the 401 incident at the same time but separately; the cause was in app code, yet its effect crossed into the website through shared infrastructure.
tags: [observability, design-tree, teams, ownership]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T16:40:00Z }
status: draft
exploration: explored
---

# Team silos

Opened by [Where the originating log lived](/exploration/log-location.md). The app and
website teams each watch their own product, though both run on the
[shared platform](/exploration/shared-platform.md).

## Understanding

- In the [401 cache poisoning incident](/incidents/third-party-401-cache-poisoning.md),
  **both teams investigated at the same time, but separately**.
- The **cause was in the app's code**. Through shared infrastructure, the failure affected
  more than the app.
- There was **no blame** between the teams afterwards ("these things happen"). The problem
  is how the work was split, not friction between people.

So the failure crossed the ownership boundary, but each team's view of the system stopped
at it. Two investigations ran in parallel with no shared picture.

## Assumptions surfaced

- Any architecture option needs a **shared, cross-product view**, plus a way for the two
  teams to work an incident together, not just better tools inside each team's view.

## Questions this opened

- [Incident coordination](/exploration/incident-coordination.md): how a cross-team incident is run today.
