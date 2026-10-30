# Log

Chronological history of changes to this vault. Append-only, **newest first**, with
ISO `YYYY-MM-DD` date headings. Convert relative dates to absolute.

## 2026-10-30

- Added [Option B in detail](/decisions/adr-001-option-b-detail.md). Corrected ADR-001
  Option B to note that AWS's documented ECS setup for Application Signals uses the
  CloudWatch agent as the collector, with ADOT as the alternative (also updated in the
  diagrams page).
- Added [Option A in detail](/decisions/adr-001-option-a-detail.md) and linked it from
  ADR-001 and the decisions index.
- Added [ADR-001](/decisions/adr-001-observability-architecture.md) (proposed) in a new
  `decisions/` folder: four observability options with sketches, a comparison and
  provisional reasoning. Linked it from the root index and the session summary.
- Stopped the grill session early at the team's request. Added the
  [session summary](/exploration/summary-2026-10-30.md) and linked it from the root index.
  Left [what a callout means](/exploration/callout-meaning.md) unexplored.
- Explored [alert design](/exploration/alert-design.md): a mix of symptom- and cause-based
  alerting, with the reasoning explained. Opened
  [what a callout means](/exploration/callout-meaning.md).
- Refocused on architecture rather than incident diagnosis. Deferred
  [user-visible impact](/exploration/user-visible-impact.md),
  [cache recovery](/exploration/cache-recovery.md) and
  [refresh trigger](/exploration/refresh-trigger.md). Reframed third-party call visibility
  as [dependency call visibility](/exploration/third-party-calls.md). Added `deferred` to
  the `exploration` values. Moved on to [alert design](/exploration/alert-design.md).
- Explored [Firebase and client-side signals](/exploration/client-side-signals.md): nothing
  showed and the app looked healthy. Opened
  [user-visible impact](/exploration/user-visible-impact.md) to resolve the mismatch.
- Explored [existing tooling](/exploration/existing-tooling.md): CloudWatch Logs and Slack
  alerts; nothing else known. Moved on to
  [Firebase and client-side signals](/exploration/client-side-signals.md).
- Corrected [where the originating log lived](/exploration/log-location.md) and
  [existing tooling](/exploration/existing-tooling.md): no combined view across both
  products is known to exist. An earlier note had read too much into an answer.
- Explored [service topology](/exploration/service-topology.md) and opened
  [refresh trigger](/exploration/refresh-trigger.md). Moved on to
  [existing tooling](/exploration/existing-tooling.md).
- Explored [detection](/exploration/detection.md): found by watching after a release; most
  incidents come from user reports. Opened
  [release verification](/exploration/release-verification.md) and updated the incident
  note. Moved on to [service topology](/exploration/service-topology.md).
- Parked [third-party call visibility](/exploration/third-party-calls.md) unanswered, at
  the team's request. Moved on to [detection](/exploration/detection.md).
- Explored [shared cache provenance](/exploration/cache-provenance.md) (ElastiCache running
  Valkey) and opened [cache recovery](/exploration/cache-recovery.md). Moved on to
  [third-party call visibility](/exploration/third-party-calls.md).
- Explored [shared platform](/exploration/shared-platform.md) and opened
  [operating ownership](/exploration/operating-ownership.md). Moved on to
  [shared cache provenance](/exploration/cache-provenance.md).
- Explored [team silos](/exploration/team-silos.md), opened
  [incident coordination](/exploration/incident-coordination.md), and updated the incident
  note. Moved on to [shared platform](/exploration/shared-platform.md).
- Explored [shape of a good outcome](/exploration/good-outcome.md) and opened
  [mitigate or solve](/exploration/mitigate-vs-solve.md). First breadth-first pass complete:
  every top-level branch explored. Second level begins with
  [team silos](/exploration/team-silos.md).
- Explored [constraints](/exploration/constraints.md): AWS is the platform, outside tools
  need procurement, and cost must be considered. Opened
  [procurement path](/exploration/procurement-path.md) and
  [other constraints](/exploration/other-constraints.md). Moved on to
  [shape of a good outcome](/exploration/good-outcome.md).
- Explored [audience and use](/exploration/audience-and-use.md). Opened
  [Firebase and client-side signals](/exploration/client-side-signals.md) and
  [alert design](/exploration/alert-design.md). Moved on to
  [constraints](/exploration/constraints.md).
- Explored [current estate](/exploration/current-estate.md): WAF, then CloudFront, then a
  load balancer, then ECS services running one image. Opened
  [service topology](/exploration/service-topology.md) and
  [existing tooling](/exploration/existing-tooling.md). Moved on to
  [audience and use](/exploration/audience-and-use.md).
- Switched questioning to breadth-first. Parked [team silos](/exploration/team-silos.md)
  and moved on to [current estate](/exploration/current-estate.md).
- Explored [where the originating log lived](/exploration/log-location.md): the gap is
  correlation, not aggregation. Opened [team silos](/exploration/team-silos.md) and
  [shared platform](/exploration/shared-platform.md), and updated the incident note.
- Explored [Motivation](/exploration/motivation.md). Added the
  [third-party 401 cache poisoning](/incidents/third-party-401-cache-poisoning.md) incident
  in a new `incidents/` folder, and opened four sub-questions: log location, cache
  provenance, third-party call visibility and detection.
- Started a grill-me session on observability architecture options. Added the root
  [exploration note](/exploration/observability-architecture.md) and five unexplored
  branches: motivation, current estate, audience and use, constraints, and shape of a good outcome.
- Vault created in Open Knowledge Format (OKF v0.2).
