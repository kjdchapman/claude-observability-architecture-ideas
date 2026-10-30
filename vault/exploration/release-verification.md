---
type: Design Question
title: Release verification
description: After a release, what does the team check (dashboards, logs, clicking through the app), for how long, and would an automated post-deploy check have caught the 401 cache poisoning?
tags: [observability, design-tree, releases, detection]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:15:00Z }
status: draft
exploration: unexplored
---

# Release verification

Opened by [Detection](/exploration/detection.md). Watching after a release is the only
reason the [401 incident](/incidents/third-party-401-cache-poisoning.md) was caught before
users reported it. Note that the failing call ran only on cache refresh, which may happen
after a short check has ended. Related: [cache recovery](/exploration/cache-recovery.md).

## Understanding

Not yet explored.
