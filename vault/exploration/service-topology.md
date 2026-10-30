---
type: Design Question
title: Service topology
description: One ECS service serves the app and several serve the website, split by request path; all run the same Docker image, with CloudFront routing by path.
tags: [observability, design-tree, aws, ecs]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T17:25:00Z }
status: draft
exploration: explored
---

# Service topology

Opened by [Current estate](/exploration/current-estate.md). Related:
[shared platform](/exploration/shared-platform.md).

## Understanding

- **One ECS service for the app.**
- **Several ECS services for the website**, split by **request path**. CloudFront routes
  each path to its service.
- All of them run **the same Docker image**.

In the [401 incident](/incidents/third-party-401-cache-poisoning.md), the failing call was
in the app's code, but the shared Valkey cache carried its effect into the website's
services.

## Assumptions surfaced

- Because every service runs the same image, telemetry has to carry the **service name**
  (and the product: app or website). Otherwise all output looks the same, and "which one
  did it?" can't be answered.
- Assumed but unconfirmed: no separate worker service exists, so the cache refresh runs
  inside the services that handle requests.

## Questions this opened

- [Refresh trigger](/exploration/refresh-trigger.md): what triggers a cache refresh, and in which service.
