---
type: Design Question
title: Audience and use
description: AWS observability is looked at only occasionally; the app team watches Firebase more, and Slack alerts on CPU and load balancer latency missed the 401 incident.
tags: [observability, design-tree, users, alerting]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T16:05:00Z }
status: draft
exploration: explored
---

# Audience and use

Branch of the [observability architecture exploration](/exploration/observability-architecture.md):
the people and moments the architecture serves.

## Understanding

- AWS observability data is looked at **only occasionally** outside incidents.
- The **app team checks Firebase** fairly often, more than the AWS side. Their main view
  of health is client-side.
- **Alerts go to a Slack channel** that both teams check. They cover **CPU** and **load
  balancer latency**, and **didn't detect** the
  [401 cache poisoning incident](/incidents/third-party-401-cache-poisoning.md). Serving a
  cached error is fast and cheap, so neither signal moved.
- The team isn't confident the current alerts are the right ones.

## Assumptions surfaced

- Infrastructure-health alerts (CPU, latency) were assumed to cover "the service is
  broken". The incident shows a correctness failure can leave both looking healthy.

## Questions this opened

- [Firebase and client-side signals](/exploration/client-side-signals.md): what the app team sees there, and whether it showed the incident.
- [Alert design](/exploration/alert-design.md): what should alert, and who acts on it. Related to [detection](/exploration/detection.md).
- The website team's habits are unknown; see [team silos](/exploration/team-silos.md).
