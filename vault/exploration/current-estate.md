---
type: Design Question
title: Current estate
description: Requests pass through WAF, then CloudFront (which also routes), then a load balancer, then one of several ECS services that all run the same Docker image.
tags: [observability, design-tree, aws, current-state]
generated: { by: claude-code/claude-opus-5-5, at: 2026-10-30T15:50:00Z }
status: draft
exploration: explored
---

# Current estate

Branch of the [observability architecture exploration](/exploration/observability-architecture.md):
what exists today, which any architecture has to start from.

## Understanding

Request path for a page that shows third-party data:

1. **AWS WAF**
2. **CloudFront**, which also does the routing to the load balancer
3. **Load balancer**
4. **The relevant ECS service**. There are several ECS services, and **all run the same
   Docker image**.

Already known from [Motivation](/exploration/motivation.md): a shared cache sits somewhere
behind the ECS tasks, the services call a third-party data provider, and logs are
centralised and searchable ([details](/exploration/log-location.md)).

Each hop (WAF, CloudFront, load balancer, ECS) produces its own logs and request IDs, so
following one request end to end means joining them.

## Questions this opened

- [Service topology](/exploration/service-topology.md): why several ECS services from one image, and what each serves.
- [Existing tooling](/exploration/existing-tooling.md): which observability tools and signals are already in use.
- Where the shared cache lives is still unknown; it belongs under [shared cache provenance](/exploration/cache-provenance.md).
