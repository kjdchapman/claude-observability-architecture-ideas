---
type: Design Question
title: Constraints
description: AWS must remain the platform (hard rule); outside observability tools may be considered but need procurement; cost must be weighed for every option.
tags: [observability, design-tree, constraint, aws, procurement]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T16:15:00Z }
status: draft
exploration: explored
---

# Constraints

Branch of the [observability architecture exploration](/exploration/observability-architecture.md):
hard requirements and preferences that narrow the options.

## Understanding

- **AWS must be the platform.** This is a hard constraint.
- **Outside tools** (for example Datadog, Grafana Cloud, Honeycomb) **can be considered**,
  but **need procurement**. They aren't ruled out, but they cost extra effort and time.
- **Cost must be considered**, for AWS-native and outside options alike.
- In practice, AWS-native options (CloudWatch, X-Ray, Application Signals and similar) are
  the low-friction default. An outside tool has to earn its procurement.

## Assumptions surfaced

- "AWS must be the platform" is read as: services stay on AWS, and observability builds on
  AWS by default. This reading hasn't been checked word for word.

## Questions this opened

- [Procurement path](/exploration/procurement-path.md): how long it takes and what a case needs.
- [Other constraints](/exploration/other-constraints.md): how cost is judged, compliance and data residency, team skills.
