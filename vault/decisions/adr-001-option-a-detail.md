---
type: Option Detail
title: "ADR-001 Option A in detail: CloudWatch quick wins"
description: A step-by-step starting sequence for Option A (zero-code alarms first, then canaries, structured logs, metrics, alert routing and a shared dashboard), with the choices inside each step and their trade-offs.
tags: [observability, aws, cloudwatch, adr, options]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T19:30:00Z }
status: draft
---

# ADR-001 Option A in detail: CloudWatch quick wins

Expands Option A of [ADR-001](/decisions/adr-001-observability-architecture.md). It is a
draft from a prototyping session. Details of AWS services come from general product
knowledge and **should be checked against current AWS documentation and pricing** before
anything is built. Effort ratings (S/M/L) are relative guesses, not estimates.

## The idea

Get the most out of what's already in place (CloudWatch, the load balancer, CloudFront,
Slack) before adding new platforms. Option A mainly targets **P2, finding out from users**,
and makes a start on P1 (correlation) and P3 (one shared view). See the
[session summary](/exploration/summary-2026-10-30.md).

One property of the [current estate](/exploration/current-estate.md) helps a lot: **every
service runs the same Docker image**. A logging change made once in that image reaches the
app and every website service.

## Where to start: a sequence

The order runs from most value for least effort to more involved work. Each step is useful
on its own, so you can stop at any point.

### Step 0: agree conventions and an owner (S)

Before writing any code, agree:

- **The log field names** every line will carry (Step 3). Use OpenTelemetry's semantic
  convention names where they exist, such as `service.name` and
  `http.response.status_code`, so moving to Option B, C or D later doesn't mean renaming
  everything.
- **Who looks after the alerts and the dashboard.** Without an owner, alerts go stale and
  get muted ([operating ownership](/exploration/operating-ownership.md)).
- **Which alerts go where.** This depends on
  [what a callout means](/exploration/callout-meaning.md).

### Step 1: alarms on metrics you already have, no code (S)

The load balancer and CloudFront already publish error metrics to CloudWatch.

- Load balancer: target 4xx and 5xx counts (responses from your ECS services), load
  balancer 5xx counts, and unhealthy host count.
- CloudFront: 4xx and 5xx error rates, per distribution. Some extra metrics need
  CloudFront's additional metrics turned on, which costs extra.
- ElastiCache: evictions, CPU, memory and connections. These show the cache's health, not
  whether its contents are correct.

Alarm on **error rates** rather than raw counts, per target group, so the app and website
paths alert separately but sit on one shared alarm list.

| Choice | Option | Trade-off |
|---|---|---|
| Threshold type | **Static threshold** (for example, 5xx rate above 2% for 5 minutes) | Simple and predictable. Needs tuning, and misses slow drift |
| | **CloudWatch anomaly detection** | Adapts to daily traffic patterns. Can be noisy until it has learned, harder to reason about, and costs more per alarm |
| Noise control | **Composite alarms** (for example, page only if the 5xx rate *and* the canary both fail) | Fewer false alarms, but more setup, and slightly later to fire |

**Limitation:** if a failure is served as **HTTP 200 with an error or empty body**, none of
these move. Whether that happened in the incident is unknown
([deferred](/exploration/user-visible-impact.md)). That gap is why Step 2 exists.

### Step 2: synthetic canaries on key journeys (S to M)

CloudWatch Synthetics runs scheduled scripts (headless browser or API calls) against your
endpoints and records pass or fail as metrics.

- Cover one or two **key journeys per product**, especially pages that show third-party
  data.
- **Check the content, not just the status code**, for example that expected data is
  present and that no error marker appears. That catches a cached error served as 200.
- Alarm on canary failures. These are **symptom-based** alerts: they mean users are
  affected now.

| Choice | Option | Trade-off |
|---|---|---|
| Canary type | **API canary** (calls the backend directly) | Cheap and stable. Misses front-end and CloudFront problems |
| | **Browser canary** (loads the real page) | Tests the whole user path through WAF, CloudFront and the load balancer. Slower, more brittle, costs more per run |
| Frequency | Every 1 minute | Detects within minutes. Highest cost (canaries are priced per run) |
| | Every 5 to 15 minutes | Cheaper. Takes longer to detect |
| Location | One region | Simple. Doesn't show regional CloudFront problems |

Canaries are the quickest way to **find out before users report it**. They are the
closest thing in Option A to the goals in [alert design](/exploration/alert-design.md).

### Step 3: structured logging in the shared image (M)

Change logging once in the shared image so every line is JSON with consistent fields:

| Field | Why |
|---|---|
| `service.name`, `product` (app or website), `deployment.version`, task ID | Answers "which one did it?" when every service runs the same image |
| `trace_id`: the load balancer's `X-Amzn-Trace-Id` header for requests | Joins load balancer access logs to app logs for the same request |
| `job_id` for work that isn't a request, such as cache refreshes | Requests get an ID for free; background work doesn't. A refresh needs its own ID |
| `dependency.name`, `http.response.status_code`, `duration_ms` on every outbound call | Shows which caller got a 401 from the third party ([dependency call visibility](/exploration/third-party-calls.md)) |
| `cache.op` (read or write), `cache.key`, `cache.write_source` (`job_id`), `cache.value_ok` | Basic cache provenance: you can search for which job wrote which key, and whether the value was an error |

**Cheap provenance:** also store the `job_id` and time alongside the cached value (an app
change). A bad value read anywhere then leads back to the log line of the job that wrote
it. This is the low-tech version of the trace links in Option B
([cache provenance](/exploration/cache-provenance.md)).

| Choice | Option | Trade-off |
|---|---|---|
| Correlation ID | **Reuse the load balancer's `X-Amzn-Trace-Id`** | Free and already present on requests. Doesn't cover background jobs, and isn't a full trace context |
| | **Your own correlation ID** | Covers everything consistently. More code, and nothing in AWS understands it |
| Verbosity | Log every outbound call and cache write | Full picture. Raises log ingestion cost |
| | Log failures plus a sample of successes | Cheaper. Successful paths are harder to compare |

### Step 4: turn log fields into metrics (S to M)

| Option | How | Trade-off |
|---|---|---|
| **Metric filters** | CloudWatch counts matching log lines, for example `status >= 400 AND dependency.name = "third-party"` | No code change after Step 3, and easy to add. Only counts and simple values, and each filter is a separate thing to maintain |
| **Embedded Metric Format (EMF)** | The app writes specially shaped JSON log lines, which CloudWatch turns into metrics automatically | Rich metrics with dimensions (by caller, by service). Needs code, and dimension combinations multiply metric cost |
| **PutMetricData API** | The app calls the CloudWatch API directly | Most control. Adds network calls to the app, and is the most code |

Recommended metrics to start with (cause-based, mostly for the dashboard):

- third-party error rate, **by caller**
- count of non-success values written to the cache
- cache refresh failures
- user-facing error rate by product

Alert only on the strongest early warnings, such as any third-party 401s or any error
written to the cache. See [alert design](/exploration/alert-design.md).

### Step 5: route alerts to Slack properly (S)

| Option | Trade-off |
|---|---|
| **Amazon Q Developer in chat applications** (formerly AWS Chatbot): alarm, then SNS, then Slack | AWS-managed, formatted messages, and you can act from Slack. Limited control over message layout |
| **Alarm, then SNS, then a Lambda posting to a Slack webhook** | Full control over content and routing. Your own code to maintain |

Use **separate channels or severities**: a "users affected" channel for symptom alarms,
and an "early warning" channel for cause alarms. One noisy channel is how today's alerts
became background noise ([audience and use](/exploration/audience-and-use.md)).

### Step 6: one shared dashboard and saved queries (S)

- **One CloudWatch dashboard covering both products**: canaries, error rates per product,
  third-party health by caller, cache writes of errors, and load balancer and ECS health.
- **Saved Logs Insights queries** that search across the app's and website's log groups at
  once, for example "first third-party error in the last hour, by service and task", or
  "which job wrote cache key X".
- Treat it as a **shared** artefact that both teams use during incidents
  ([team silos](/exploration/team-silos.md),
  [incident coordination](/exploration/incident-coordination.md)).

### Optional extras

| Extra | Value | Trade-off |
|---|---|---|
| **Container Insights** for ECS | Per-task and per-service CPU, memory and network | Extra metrics cost. Helps with performance more than correctness |
| **Load balancer access logs** (to S3, queried with Athena) | Every request, with the trace ID | Storage, plus setting up Athena. Mostly useful after the fact |
| **CloudFront standard or real-time logs** | The edge view of errors by path | Real-time logs cost more. Usually not needed at first |
| **Infrequent Access log class** for bulky logs | Lower ingestion cost | Fewer features. Check whether metric filters work on it before relying on it for Step 4 |

## How Option A would have handled the incident

| Moment | Without A | With A |
|---|---|---|
| Refresh gets a 401 | One unstructured line on one task | A structured line with caller, `job_id` and status. The "third-party 401 by caller" alarm fires: an **early warning before users notice** |
| Error written to the cache | Invisible | "Non-success cache write" metric rises, and the alarm fires |
| Users get the error | Found through user reports, or by luck after a release | The canary's content check fails, and the "users affected" alarm fires |
| Investigation | Two teams searching separately | One dashboard, then a saved query, then the cached value's `job_id`, then the log of the job that wrote it |

## Trade-offs of Option A as a whole

**Strengths**
- Cheap, quick, no procurement, and builds on skills the web team already has.
- Most of the detection value (P2) comes from Steps 1, 2 and 5, which need little or no
  code.
- Nothing is wasted: the conventions, fields, canaries and alert routing all carry over to
  Option B, C or D.

**Limits**
- **Correlation is hand-made.** You only see the IDs and fields you remembered to log. No
  traces and no service map.
- **Every alarm, filter and query is maintained by hand**, which becomes a burden without
  an owner.
- **Log-based metrics get costly** as traffic and verbosity grow. Option B's native metrics
  scale better.
- **It doesn't fix silos by itself.** A shared dashboard only helps if both teams use it.

## Questions to answer before starting

- [What a callout means](/exploration/callout-meaning.md): which alarms page someone and
  which only post.
- [Operating ownership](/exploration/operating-ownership.md): who looks after the alarms
  and the dashboard.
- Which journeys are "key" for each product, to choose the canaries.
- The services' programming language, for the structured-logging library.
- How cost is judged ([other constraints](/exploration/other-constraints.md)): this decides
  canary frequency and how much to log.
