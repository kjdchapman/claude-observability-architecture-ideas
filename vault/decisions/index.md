# Decisions

Architecture decision records (ADRs). In this prototyping vault they set out options and
reasoning. `adr_status` shows whether anything has actually been decided.

- **[ADR-001: Observability architecture for AWS-hosted services](/decisions/adr-001-observability-architecture.md)** *(proposed)*: four options compared, from CloudWatch quick wins to OpenTelemetry with AWS-native, external or AWS-managed open-source backends.
  - **[Option A in detail](/decisions/adr-001-option-a-detail.md)**: starting sequence, the choices within each step, and their trade-offs.
  - **[Option B in detail](/decisions/adr-001-option-b-detail.md)**: pilot, rollout, SLOs, refresh-job spans and cache provenance; choices of collector, sampling and instrumentation.
