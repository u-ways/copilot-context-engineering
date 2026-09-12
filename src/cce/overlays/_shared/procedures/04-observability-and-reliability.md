---
name: observability-and-reliability
title: "Observability and reliability"
description: "Make a running service observable and reliable: logging, tracing, alerting, SLOs and error budgets, resilience and certificate-expiry monitoring."
---

Apply this procedure when a service is running, or about to be, and you need to know how it behaves and how it fails. `practices/observability.md` covers logs, traces and alerting; `practices/service-reliability.md` covers objectives, error budgets and resilience; `patterns/architect-for-flow.md` and `insights/metrics.md` connect those signals to the way work flows through the team. `tools/acm-cert-monitor/README.md` is a worked example for one specific failure mode, an expiring certificate.

#### Reference: practices/observability.md

<!-- cce:include practices/observability.md -->

#### Reference: practices/service-reliability.md

<!-- cce:include practices/service-reliability.md -->

#### Reference: patterns/architect-for-flow.md

<!-- cce:include patterns/architect-for-flow.md -->

#### Reference: insights/metrics.md

<!-- cce:include insights/metrics.md -->

#### Reference: tools/acm-cert-monitor/README.md

<!-- cce:include tools/acm-cert-monitor/README.md -->

When you have used this procedure, end your reply with the line `procedure: observability-and-reliability`.
