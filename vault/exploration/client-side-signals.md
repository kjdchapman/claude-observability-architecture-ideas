---
type: Design Question
title: Firebase and client-side signals
description: During the 401 incident Firebase raised no alerts and showed nothing at a quick look, and the app looked healthy when checked, so client-side signals didn't reveal it.
tags: [observability, design-tree, firebase, client-side]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:50:00Z }
status: draft
exploration: explored
---

# Firebase and client-side signals

Opened by [Audience and use](/exploration/audience-and-use.md). The app team watches
Firebase more than AWS. Related: [detection](/exploration/detection.md).

## Understanding

During the [401 cache poisoning incident](/incidents/third-party-401-cache-poisoning.md):

- **No alerts from Firebase.**
- **Nothing visible** in Firebase from a quick look.
- **Checking the app by hand showed it healthy.**

So client-side signals missed it too, alongside the AWS alerts.

## Assumptions surfaced

- This doesn't fit the claim that the poisoned cache broke every ECS task. Either the app
  handled the cached error without showing it (for example, rendering empty or stale data
  without crashing), or the damage showed somewhere other than the app. See
  [user-visible impact](/exploration/user-visible-impact.md).

## Questions this opened

- [User-visible impact](/exploration/user-visible-impact.md): what users actually saw, and where.
