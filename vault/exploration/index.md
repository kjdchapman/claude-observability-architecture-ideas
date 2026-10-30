# Exploration

The design tree from questioning sessions on observability architecture. Each note is one
question; its `exploration` field shows whether it is `unexplored`, `exploring`, `explored`
or `deferred` (out of scope).

- **[Observability architecture exploration](/exploration/observability-architecture.md)**: root of the tree.
- **[Session summary, 2026-10-30](/exploration/summary-2026-10-30.md)**: where the first session got to. Start here.
- **[Motivation](/exploration/motivation.md)**: what is wrong or missing today.
  - **[Where the originating log lived](/exploration/log-location.md)**: correlation gap, not aggregation.
    - **[Team silos](/exploration/team-silos.md)**: both teams investigated at once, separately; the cause was in app code.
      - **[Incident coordination](/exploration/incident-coordination.md)**: how cross-team incidents are run.
    - **[Shared platform](/exploration/shared-platform.md)**: jointly owned, effectively unowned; the web team knows the infrastructure best.
      - **[Operating ownership](/exploration/operating-ownership.md)**: who would run the observability setup.
  - **[Shared cache provenance](/exploration/cache-provenance.md)**: ElastiCache running Valkey; what was written is unknown.
    - **[Cache recovery](/exploration/cache-recovery.md)** *(deferred)*: how the bad entry was cleared; TTL.
  - **[Dependency call visibility](/exploration/third-party-calls.md)**: whether calls to external dependencies should be first-class telemetry.
  - **[Detection](/exploration/detection.md)**: caught by watching after a release; usually found through user reports.
    - **[Release verification](/exploration/release-verification.md)**: what gets checked after a release.
- **[Current estate](/exploration/current-estate.md)**: WAF, CloudFront, load balancer, several ECS services on one image.
  - **[Service topology](/exploration/service-topology.md)**: one app service, several website services split by path.
    - **[Refresh trigger](/exploration/refresh-trigger.md)** *(deferred)*: what triggers a cache refresh, and where it runs.
  - **[Existing tooling](/exploration/existing-tooling.md)**: CloudWatch Logs and Slack alerts; nothing else known.
- **[Audience and use](/exploration/audience-and-use.md)**: AWS data checked occasionally; Firebase watched more; alerts missed the incident.
  - **[Firebase and client-side signals](/exploration/client-side-signals.md)**: showed nothing; the app looked healthy.
    - **[User-visible impact](/exploration/user-visible-impact.md)** *(deferred)*: what users actually saw, and where.
  - **[Alert design](/exploration/alert-design.md)**: a mix of symptom- and cause-based alerts, reasoning explained; know before a callout.
    - **[What a callout means](/exploration/callout-meaning.md)**: an on-call page, a customer call, or something else.
- **[Constraints](/exploration/constraints.md)**: AWS is the platform; outside tools need procurement; cost matters.
  - **[Procurement path](/exploration/procurement-path.md)**: what it takes to bring in an outside tool.
  - **[Other constraints](/exploration/other-constraints.md)**: how cost is judged; compliance; skills.
- **[Shape of a good outcome](/exploration/good-outcome.md)**: problem statement, several sketched options, a reasoned comparison.
  - **[Mitigate or solve](/exploration/mitigate-vs-solve.md)**: where the line between the two falls.
