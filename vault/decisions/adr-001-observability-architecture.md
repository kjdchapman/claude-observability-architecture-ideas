---
type: Architecture Decision Record
title: "ADR-001: Observability architecture for AWS-hosted services"
description: Proposed, not decided. Compares four options, from CloudWatch quick wins to OpenTelemetry with AWS-native, AWS-managed open-source or external backends, against the problems found in the 2026-10-30 grill session.
tags: [observability, aws, adr, options]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T19:00:00Z }
status: draft
adr_status: proposed
---

# ADR-001: Observability architecture for AWS-hosted services

**Status:** Proposed. This sets out options for discussion; nothing is decided. It was
produced in a prototyping session and is drafted from the
[session summary](/exploration/summary-2026-10-30.md). The claims about AWS services are
general product knowledge and haven't been checked against this account or current
pricing.

## Context

The app and the website run as several ECS services from one Docker image, behind WAF,
CloudFront and a load balancer, and share an ElastiCache (Valkey) cache
([current estate](/exploration/current-estate.md),
[service topology](/exploration/service-topology.md)). Current tooling is CloudWatch Logs,
Slack alerts on CPU and load balancer latency, and Firebase on the app side
([existing tooling](/exploration/existing-tooling.md)).

In the [third-party 401 cache poisoning incident](/incidents/third-party-401-cache-poisoning.md),
one failing call put an error into the shared cache, and every task served it. The cause
was logged once, on one task. No alert fired. Two teams investigated separately.

The problems to address:

- **P1, correlation.** Logs are collected, but nothing links an effect to its cause across
  tasks, services and products ([details](/exploration/log-location.md)).
- **P2, detection.** Incidents are usually found through user reports. Alerts watch
  infrastructure strain, not correctness ([detection](/exploration/detection.md)).
- **P3, silos.** Each team watches only its own product. The shared infrastructure is
  effectively unowned ([team silos](/exploration/team-silos.md),
  [shared platform](/exploration/shared-platform.md)).

## Decision drivers

1. **Know before users do.** Ideally before a callout, definitely before a poor user
   experience ([alert design](/exploration/alert-design.md)).
2. **Trace an effect to its origin** across tasks, services and both products.
3. **One view both teams can use**, including the team less familiar with AWS.
4. **AWS stays the platform.** Outside tools need procurement. Cost matters
   ([constraints](/exploration/constraints.md)).
5. **Explain the reasoning**, so the team learns how to choose, not only what was chosen
   ([shape of a good outcome](/exploration/good-outcome.md)).

## Two distinctions used throughout

**Mitigate or solve.** A *mitigation* shortens how long a failure goes unnoticed or how far
it spreads, without explaining it. A *solution* makes the cause findable directly. Both are
wanted ([mitigate or solve](/exploration/mitigate-vs-solve.md)). The working definition
here is ours and still needs the team to agree it.

**Symptom-based or cause-based alerts.**

| | Symptom-based ("users are affected") | Cause-based ("this component is failing") |
|---|---|---|
| Examples | User-facing error rate, failing synthetic checks of key pages, missed latency targets | Dependency 4xx/5xx, errors being cached, failed cache refreshes |
| Why use it | Every alert matters to users, so there are few false alarms and it catches failures nobody predicted | Points at the culprit and can fire **before** users notice |
| Why not rely on it alone | Fires only once users are already affected; doesn't say why | You must predict each failure mode; more alerts; noisier |
| Rule of thumb | **Route to Slack or paging**: something is wrong now | **Put on dashboards; alert only on the few strong early warnings** |

The incident would have been caught by a symptom alert (a canary seeing errors) and
explained by a cause signal (dependency 401s from one caller). That's why all the options
below include both.

## Considered options

Option A works on its own, and is also the first step of B, C or D. B, C and D are
alternatives to one another and differ mainly in where telemetry is stored and viewed.

### Option A: CloudWatch quick wins (mitigation)

Get more from what already exists. No new services to procure.

```
 app + website ECS tasks ──structured JSON logs──► CloudWatch Logs ──metric filters──► CloudWatch metrics
   (service, product, trace id,                        │                                      │
    dependency, status, cache_write)                   └─ Logs Insights saved queries         ▼
                                                          (across both products)       CloudWatch alarms ──► Slack
 CloudWatch Synthetics canaries ──► key app and website pages/APIs ────────────────────────────┘
 Shared CloudWatch dashboard: both products, dependencies, cache, canaries
```

- **Structured logs** with consistent fields on every line: service, product (app or
  website), task ID, the load balancer's `X-Amzn-Trace-Id` request header, dependency name,
  status code, and whether this line is a cache write.
- **Metric filters and alarms** on those fields, for example "third-party responses with
  status ≥ 400 by caller" and "cache writes of non-success responses".
- **Synthetic canaries** that load key pages and APIs for both products and check the
  content, not just the status code.
- **One shared dashboard** and saved cross-product queries.

**Addresses:** P2 well; P1 partly (the request ID joins load balancer and app logs, but
nothing follows work that isn't a request, such as a cache refresh); P3 partly (one shared
view).
**Pros:** cheap; quick; no procurement; uses skills the web team already has; works whatever
the code language.
**Cons:** every field and filter is hand-maintained; no traces or service map; following
cause and effect stays manual; log-based metrics get costly as volume grows.
**Fits when:** you need protection now, or the budget is tight, or as step one before B, C
or D.
**Cost shape:** log ingestion and storage, per-metric and per-alarm charges, per canary run.
Low.
**In detail:** [Option A: starting sequence, choices and trade-offs](/decisions/adr-001-option-a-detail.md).

### Option B: OpenTelemetry into AWS-native backends (solution, AWS only)

Instrument the services with OpenTelemetry, run the AWS Distro for OpenTelemetry (ADOT)
collector, and use AWS's own observability services.

```
 ECS task: [app container + OTel SDK/auto-instrumentation] ──OTLP──► [ADOT collector sidecar]
                                                                          │
                     ┌──────────────── traces ──────────────┬─── metrics ┴──── logs ───┐
                     ▼                                       ▼                          ▼
                AWS X-Ray                         CloudWatch metrics           CloudWatch Logs
                     └──────────► CloudWatch Application Signals ◄──────────────────────┘
                                 (service map, dependency calls, SLOs)
                                          │
                       SLO and anomaly alarms ──► Slack            + Synthetics canaries (from A)
```

- **Traces** follow each request through the load balancer and ECS into dependency calls.
  The failing third-party call would show up with its caller and 401 status.
- **Application Signals** gives a service map, per-dependency health, and SLOs (service
  level objectives) for both products in one console.
- **Cache provenance (an app change):** store the writer's trace ID, service and time
  alongside each cached value. When a request reads a bad entry, it can link to the trace
  that wrote it. **Tracing alone does not connect "wrote bad data" with "read bad data
  later"**, and this link is what solves the incident's exact problem.

**Addresses:** P1 well (together with cache provenance); P2 well (SLOs plus canaries);
P3 well (one service map across both products).
**Pros:** no procurement; vendor-neutral instrumentation (OpenTelemetry), so the backend
can be swapped later for C; built-in service map and SLOs; stays inside AWS IAM and
billing.
**Cons:** the AWS consoles are less fluid for open-ended investigation than specialist
tools; costs for tracing and Application Signals grow with traffic, so sampling needs
tuning; automatic instrumentation support depends on the language; still effectively owned
by the web team unless ownership changes.
**Fits when:** AWS-only is preferred, procurement is slow, and the team wants built-in
"what calls what" without building dashboards itself.
**Cost shape:** per trace recorded or scanned, Application Signals per request or signal,
metrics and logs as in A. Medium, controlled by sampling.
**Note:** AWS's documented ECS setup for Application Signals uses the CloudWatch agent as
the sidecar collector. The ADOT collector is the vendor-neutral alternative.
**In detail:** [Option B: starting sequence, choices and trade-offs](/decisions/adr-001-option-b-detail.md).

### Option C: OpenTelemetry into an external observability product (solution, needs procurement)

The same instrumentation as B, but the collector exports to an outside product such as
Honeycomb, Datadog or Grafana Cloud.

```
 ECS task: [app + OTel SDK] ──OTLP──► [OTel/ADOT collector sidecar] ──OTLP/HTTPS──► External product
                                              │                                   (traces, metrics, logs,
                                              └──(optional) CloudWatch Logs           SLOs, alerting) ──► Slack
 CloudWatch metrics for AWS-managed services ──integration──► External product
```

**Addresses:** P1 very well, P2 well, P3 well, with a better investigation experience.
**Pros:** fast, flexible querying across fields with many distinct values, such as "all
401s by caller and task over the last hour"; a single place to look, which suits a team
less fluent in AWS; strong alerting and SLO tooling; OpenTelemetry keeps lock-in low.
**Cons:** **needs procurement** (time, security review, contract); data leaves AWS, so a
compliance question needs answering ([other constraints](/exploration/other-constraints.md));
pricing models differ a lot (per host, per GB ingested, per event) and can surprise;
another vendor to manage.
**Fits when:** speed of investigation and cross-team usability matter more than staying
AWS-only, and procurement is realistic ([procurement path](/exploration/procurement-path.md)).
**Cost shape:** vendor-dependent, usually the highest at scale, but the most predictable
with event-based pricing.

### Option D: OpenTelemetry into AWS-managed open-source backends (solution, AWS-billed)

The same instrumentation, exported to Amazon Managed Service for Prometheus (metrics),
X-Ray or Amazon OpenSearch (traces and logs), and viewed in Amazon Managed Grafana.

```
 ECS task: [app + OTel SDK] ──► [ADOT collector] ──metrics──► Amazon Managed Prometheus ─┐
                                        ├──────traces──────► X-Ray / OpenSearch ─────────┼─► Amazon Managed Grafana
                                        └──────logs────────► CloudWatch Logs ────────────┘    (dashboards, alerts ──► Slack)
```

**Addresses:** P1 well, P2 well, P3 well, if the team builds the dashboards.
**Pros:** billed through AWS, which probably avoids a separate procurement (not yet
confirmed); open standards (PromQL, Grafana); flexible dashboards that both teams can
share.
**Cons:** the most to put together and maintain, with no built-in service map or SLOs like
B's; needs Prometheus and Grafana skills the team may not have; several services to keep
running when no one clearly owns them.
**Fits when:** the team wants open-source tooling and flexibility without an outside
vendor, and someone will own the platform
([operating ownership](/exploration/operating-ownership.md)).
**Cost shape:** Grafana per user, Prometheus per sample ingested and queried, trace
storage. Medium.

## Comparison

| | A: CloudWatch quick wins | B: OTel + AWS-native | C: OTel + external product | D: OTel + AWS-managed OSS |
|---|---|---|---|---|
| Mitigate or solve | Mitigate | Solve | Solve | Solve |
| P1 correlation | ◐ request-scoped only | ● with cache provenance | ● with cache provenance | ● with cache provenance |
| P2 detection | ● canaries and filters | ● plus SLOs | ● plus SLOs | ◐ SLOs built by hand |
| P3 shared view | ◐ one dashboard | ● service map | ● best for cross-team use | ◐ depends on dashboards built |
| Procurement | None | None | **Required** | Probably none (unconfirmed) |
| Relative cost | Low | Medium | Medium to high | Medium |
| Effort to adopt | Low | Medium | Medium | High |
| Ongoing ownership load | Low | Low to medium | Low (vendor runs it) | High |
| Lock-in | AWS | Low (OTel) | Low (OTel) | Low (OTel, open source) |

● strong · ◐ partial

## Applies to every option

These come from the grill and are not about tooling. Without them, no option fixes P3.

- **Telemetry conventions:** every signal carries `service.name`, the product (app or
  website), the deployment version and the task. All services run one image, so without
  these, "which one did it?" can't be answered
  ([service topology](/exploration/service-topology.md)).
- **Cache provenance and error handling:** record who wrote each cache entry, and don't
  cache responses that aren't successes. This is an app change, but it's what makes the
  incident's cause findable.
- **Dependency calls as first-class signals:** status, latency and caller for every
  outbound call ([dependency call visibility](/exploration/third-party-calls.md)).
- **A named owner** for the observability setup and the shared components
  ([operating ownership](/exploration/operating-ownership.md)).
- **A shared incident practice:** one channel and one view when an incident spans both
  products ([incident coordination](/exploration/incident-coordination.md)).

## Decision

**Not decided.**

Provisional reasoning, for discussion: **do A now, and choose between B and C next**.

- A addresses the most painful problem (P2: finding out from users) within days, at low
  cost and with no procurement. It's also groundwork B, C and D all need.
- Between B and C, the deciding question is whether procurement and cost are acceptable in
  exchange for faster investigation and easier use across teams. B is the default because
  it needs no procurement. Because both use OpenTelemetry, starting on B keeps C open later.
- D is ranked last only because ownership is unclear today. D adds the most platform to
  run, and no one currently owns shared things.

## Consequences

- **Choosing A only:** faster detection, but diagnosis stays manual. A repeat of the
  incident would be *noticed* sooner but still *diagnosed* slowly.
- **Choosing B, C or D:** code changes for instrumentation and cache provenance, a
  collector sidecar in each ECS task, a new recurring cost, and a need for an owner.
- **Not choosing:** detection keeps relying on users and luck after releases.

## Open questions that could change this

- [What a callout means](/exploration/callout-meaning.md): it decides what pages a person
  versus posts to Slack.
- [Operating ownership](/exploration/operating-ownership.md): with no owner, the case for
  D weakens and the case for C strengthens.
- [Procurement path](/exploration/procurement-path.md) and
  [other constraints](/exploration/other-constraints.md): time to procure, how cost is
  judged, and whether telemetry may leave AWS.
- The services' programming language (not yet asked): it decides how much automatic
  instrumentation is available for B, C and D.
