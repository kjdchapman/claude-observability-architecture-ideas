---
type: Option Detail
title: "ADR-001 Option B in detail: OpenTelemetry into AWS-native backends"
description: A starting sequence for Option B (pilot one ECS service with auto-instrumentation and Application Signals, then roll out, add SLOs, refresh-job spans and cache provenance), with the choices and trade-offs at each step.
tags: [observability, aws, opentelemetry, x-ray, application-signals, adr, options]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T20:00:00Z }
status: draft
---

# ADR-001 Option B in detail: OpenTelemetry into AWS-native backends

Expands Option B of [ADR-001](/decisions/adr-001-observability-architecture.md). It is a
draft from a prototyping session. Details of AWS services come from general product
knowledge and **should be checked against current AWS documentation and pricing**. Product
names and features in this area change often. Effort ratings (S/M/L) are relative guesses.

## The idea

Add **distributed tracing** and **application-level metrics** using OpenTelemetry (OTel),
and view them in AWS's own tools: **X-Ray** for traces, **CloudWatch** for metrics and
logs, and **CloudWatch Application Signals** for a service map, per-dependency health and
SLOs. This is a *solution* option: it makes causes findable, where Option A only spots
symptoms sooner. It builds on [Option A](/decisions/adr-001-option-a-detail.md), and works
best after A's Step 0 conventions and Step 2 canaries are in place.

## What each piece does

| Piece | What it gives you |
|---|---|
| **OTel SDK or auto-instrumentation** in the app | Spans for incoming requests, outgoing HTTP calls (such as the third party) and cache commands, without hand-written code in supported languages |
| **Collector** in each task (a **CloudWatch agent** or **ADOT collector** sidecar) | Receives telemetry from the app, adds ECS context, samples, and sends it to AWS |
| **X-Ray** | Traces: one request's path through the load balancer, ECS, the third party and Valkey, with timings and errors |
| **Application Signals** | Service map; request, error and fault rates per service and per dependency; SLOs with burn-rate alarms |
| **CloudWatch Logs** | The structured logs from Option A, now with trace IDs, so you can jump from a trace to its log lines |

**Correction to ADR-001's diagram:** AWS's documented ECS setup for Application Signals
uses the **CloudWatch agent** as the sidecar, plus an **init container** that supplies the
auto-instrumentation agent. A plain **ADOT collector** is the alternative when you don't
use Application Signals, or want vendor-neutral collector config. Both are covered below.
Check the current docs, because this has changed over time.

## Where to start: a sequence

### Step 0: prerequisites (S)

- **Option A's Step 0 conventions** (field names, owner, alert routing), and ideally its
  canaries.
- **Find out the services' language and framework.** This decides how much
  auto-instrumentation works. Application Signals auto-instrumentation has supported Java,
  Python, .NET and Node.js; anything else needs the SDK added by hand.
- **Pick a pilot service.** The app service is the obvious choice: it's where the incident
  started, and it calls the third party. One website path service is the lower-risk
  alternative.

### Step 1: pilot one service with auto-instrumentation (M)

- Turn on Application Signals in the account.
- Add the **collector sidecar** and the **auto-instrumentation init container** to the
  pilot's task definition. This should need **no application code change** in a supported
  language.
- **Set the service identity in the task definition, not the image**, because the image is
  shared. For example, `OTEL_SERVICE_NAME=website-path-1` and
  `OTEL_RESOURCE_ATTRIBUTES=product=website,deployment.environment=prod`.
- Have the app **accept both trace header formats**: AWS's `X-Amzn-Trace-Id` and W3C
  `traceparent`. The load balancer adds `X-Amzn-Trace-Id`, so the trace starts at the load
  balancer.

### Step 2: check value, overhead and cost (S)

Before rolling out, confirm that:

- the **service map** shows the pilot, the **third party** and **Valkey** as dependencies
- **dependency error rates** appear. Application Signals separates *errors* (4xx, so a 401
  from the third party) from *faults* (5xx)
- **overhead** is acceptable: task CPU and memory, plus any added latency
- **daily cost** at real traffic, to set sampling before going wider

### Step 3: roll out to all services (S to M)

The same task-definition change on every service, each with its own `OTEL_SERVICE_NAME`
and `product`. The app and all website services then show on **one service map**: one view
for both teams ([team silos](/exploration/team-silos.md)).

### Step 4: SLOs and alerting (S to M)

- Define **SLOs for each product's key operations**, for example "99.5% of requests to
  pages showing third-party data succeed".
- Alarm on **burn rate**: how fast the error budget is being used up. This is a better
  symptom-based alert than a fixed error threshold. A fast burn means users are being hurt
  now; a slow burn can wait for working hours.
- Add **dependency alarms**, for example the third party's error rate by calling service.
  These are the cause-based early warnings from [alert design](/exploration/alert-design.md).
- Route alerts to the same two Slack channels as Option A's Step 5.

### Step 5: what auto-instrumentation misses: refresh jobs and cache provenance (M)

Auto-instrumentation traces **requests**. A cache refresh that runs on a timer or in the
background may not be traced, or may be attached to whichever request happened to trigger
it.

- Add a **manual span** around each refresh job, with attributes for the job, the
  dependency, the status and the cache key.
- **Cache provenance (an app change):** store the writer's **trace ID**, service and time
  alongside each cached value. On read, add a **span link** to the writer's trace. From any
  bad read, the link leads to the exact refresh that wrote it.
- **Don't cache failed responses.** This isn't observability, but it's the fix that stops
  the poisoning altogether.

This step is what solves the incident's specific problem. Tracing alone **does not**
connect "wrote bad data" with "read bad data later".

### Step 6: link logs to traces (S)

Put the trace ID and span ID into every structured log line. The OTel logging integrations
do this for common logging libraries. You can then go from a trace to its log lines, and
from a log line to its trace.

## Choices and trade-offs

| Choice | Option | Trade-off |
|---|---|---|
| **Collector** | **CloudWatch agent** (the Application Signals route) | Best-supported path to Application Signals, and simplest on AWS. Its config is AWS-specific |
| | **ADOT collector** (an OpenTelemetry Collector build) | Vendor-neutral config, so Option C later is mostly a config change. More to configure yourself, and check how Application Signals support works with it |
| **Where the collector runs** | **Sidecar in each task** | Isolated, scales with tasks, and adds ECS context. Small CPU and memory cost per task |
| | **One shared collector service** | Fewer containers and one config. A shared dependency that can drop everyone's telemetry at once, plus more network hops |
| **Instrumentation** | **Automatic** | Fast, no code change, broad coverage. Less control, some start-up and runtime overhead, and misses background jobs |
| | **Manual spans added on top** | Covers refresh jobs, cache provenance and business attributes. Code to write and keep up |
| **Sampling** | **Head sampling** (decide when a trace starts; X-Ray sampling rules) | Simple and cheap. Can drop the rare failing trace you need |
| | **Tail sampling** (decide after a trace completes; for example keep every error) | Keeps the interesting traces. More collector setup and memory, and it's easier with the ADOT collector |
| | **Keep 100% of spans** (for example via CloudWatch Transaction Search, which stores spans as logs) | Nothing is missed. Cost grows with traffic, so check the pricing |
| **Trace header format** | **W3C `traceparent` plus `X-Amzn-Trace-Id`** | Works with the load balancer and keeps Option C open. Both need configuring |

## How Option B would have handled the incident

| Moment | With Option B |
|---|---|
| Refresh gets a 401 | The refresh span records the third party, a 401 and the calling service. The dependency error rate for "app service → third party" rises, and the early-warning alarm fires |
| Error written to the cache | The write carries the refresh span's trace ID (Step 5), or, if errors aren't cached, the poisoning never happens |
| Users get the error | Application Signals shows a rising error rate on every service reading the cache. The SLO burn-rate alarm fires, and canaries fail |
| Investigation | Open the service map, then the failing dependency edge, then example traces. From any bad read, the span link leads to the refresh trace, its service and task, and the 401. Both teams look at the same map |

## Trade-offs of Option B as a whole

**Strengths**
- **Solves correlation (P1)**, with cache provenance added, and gives a **service map
  covering both products (P3)**.
- **No procurement.** It stays inside AWS IAM, billing and the data boundary.
- **OpenTelemetry keeps the exit open.** Moving to Option C is mostly a collector and
  backend change.
- Dependency monitoring and SLOs come built in, rather than built by hand as in Option A.

**Limits and risks**
- **Language support decides the effort.** Outside the supported languages, it's manual
  SDK work.
- **Cost grows with traffic.** Sampling and retention need setting deliberately, and
  measuring in the pilot.
- **Investigation in the console is less fluid** than in specialist tools (Option C), for
  open-ended questions like "show me every 401 by caller and task".
- **Background work needs manual instrumentation**, and cache provenance is an app change.
- **Ownership:** someone has to own the collector config, the SLOs and the alarms
  ([operating ownership](/exploration/operating-ownership.md)).

## Questions to answer before starting

- The services' **language and framework**: this decides automatic or manual
  instrumentation.
- [What a callout means](/exploration/callout-meaning.md): which SLO burn rates page
  someone.
- [Operating ownership](/exploration/operating-ownership.md): who owns the SLOs and the
  collector.
- How cost is judged ([other constraints](/exploration/other-constraints.md)): this sets
  the sampling strategy.
- Whether to keep **Option C** open, which favours the ADOT collector and W3C headers from
  the start.
