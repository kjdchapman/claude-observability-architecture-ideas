---
type: Incident
title: Third-party 401 cache poisoning
description: One call site missing the newly required third-party API key failed only on cache refresh, wrote an error into the shared cache, and broke every ECS task; only one task logged the cause.
tags: [incident, third-party, cache, ecs, authentication]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T15:20:00Z }
status: draft
---

# Third-party 401 cache poisoning

The incident that motivated this [exploration](/exploration/motivation.md), as described
by the team.

## What happened

- A third party supplies much of the data shown in our application. It recently started
  requiring an API key on every request.
- We added the key, but **one use of the endpoint was missed**. That call ran only when the
  cache was refreshed.
- When it ran, the third party returned **401 Unauthorized**, and the refresh wrote that
  **error state into the cache**.
- The cache is shared (ElastiCache running Valkey), so **every ECS task** then served the
  error. Exactly what was written is unknown; it looked like a cached error
  ([details](/exploration/cache-provenance.md)).

## How it was detected

The team noticed it while watching after a release. The Slack alerts (CPU and load
balancer latency) didn't fire. Most incidents are found through user reports
([details](/exploration/detection.md)).

## Why it was hard to diagnose

- We saw 401s from an endpoint we believed was authorised.
- **Only one error message** recorded the original failing call, and it was in
  **one ECS task's** output, while the symptoms appeared on all of them.
- Logs were centralised and searchable, but nothing linked that line to the errors seen
  elsewhere ([details](/exploration/log-location.md)).
- The app and website share the web server but are owned by separate teams, each tending
  to look only at its own product.
- Both teams investigated at the same time but separately. The missing key was in the
  app's code ([details](/exploration/team-silos.md)).
- Finding where the first error came from took a long time.

## Related questions

- [Where the originating log lived](/exploration/log-location.md)
- [Shared cache provenance](/exploration/cache-provenance.md)
- [Third-party call visibility](/exploration/third-party-calls.md)
- [Detection](/exploration/detection.md)
