---
type: Design Question
title: Existing tooling
description: Current AWS-side tooling is CloudWatch Logs plus Slack alerts on CPU and load balancer latency; no dashboards, custom metrics or tracing are known to exist.
tags: [observability, design-tree, aws, current-state, tooling, cloudwatch]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:40:00Z }
status: draft
exploration: explored
---

# Existing tooling

Opened by [Current estate](/exploration/current-estate.md).

## Understanding

- **CloudWatch Logs** holds the centralised, searchable logs from all ECS tasks
  ([details](/exploration/log-location.md)).
- **Slack alerts** on CPU and load balancer latency
  ([details](/exploration/audience-and-use.md)).
- **Firebase**, used by the app team for the client side
  ([details](/exploration/client-side-signals.md)).
- **Nothing else is known to be in place**: no dashboards, no custom or application
  metrics, no tracing, and no combined view across both products.

## Assumptions surfaced

- The starting point is close to a blank slate above basic logging. Options don't need to
  plan around replacing an existing stack, only around building on CloudWatch Logs.
- Assumed but unconfirmed: the Slack alerts are CloudWatch alarms on default ECS and load
  balancer metrics.
