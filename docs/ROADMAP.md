# PhysiqOS Roadmap

> **Last updated:** 2026-11-23 · **Current milestone:** M1 Evaluation foundation

PhysiqOS is developed as a production LLM system. Every milestone has measurable exit criteria and ships a written artifact (report, design doc or dashboard), linked here once complete. Changes to prompts, models or retrieval are evaluated against the golden set defined in [`eval-spec.md`](eval-spec.md) before merge.

**Status:** ✅ Done · 🚧 In progress · ⏳ Planned

## Overview

| Milestone                                                                  | Target date | Status | Key deliverable                         |
| -------------------------------------------------------------------------- | ----------- | ------ | --------------------------------------- |
| [M1 · Evaluation foundation](#m1--evaluation-foundation)                   | 2026-12-06  | 🚧     | Baseline eval report                    |
| [M2 · Retrieval-augmented estimation](#m2--retrieval-augmented-estimation) | 2026-12-20  | ⏳     | Ablation report                         |
| [M3 · Observability & model gateway](#m3--observability--model-gateway)    | 2027-01-03  | ⏳     | Cost & latency dashboard, design doc    |
| [M4 · Production on AWS](#m4--production-on-aws)                           | 2027-01-10  | ⏳     | Architecture diagram, CI with eval gate |
| [M5 · Launch & data flywheel](#m5--launch--data-flywheel)                  | 2027-01-17  | ⏳     | Public web app, eval set v0.2           |
| [M6 · Coach agent & plan generation](#m6--coach-agent--plan-generation)    | 2027-01-31  | ⏳     | Agent eval & red-team report            |
| [M7 · Cost optimization & operations](#m7--cost-optimization--operations)  | 2027-02-14  | ⏳     | Cost/quality Pareto curve, case study   |

## Milestones

### M1 · Evaluation foundation

**Target:** 2026-12-06 · **Status:** 🚧 In progress

**Goal:** Build a versioned golden dataset and a reproducible eval harness before any pipeline, so every later change is measured rather than eyeballed.

**Scope**

- Eval spec: task definition, metrics, ship criteria ([`eval-spec.md`](eval-spec.md))
- Golden dataset v0.1: 60 labeled text prompts, ~40 labeled images, datacard
- Eval harness: config-driven runs, per-run artifacts, unit-tested metrics
- Zero-shot baseline with structured output, followed by error analysis
- _Product:_ backend skeleton, calorie and macro target calculator (TDEE)

**Exit criteria**

- Dataset v0.1 tagged; every label traceable to a USDA FoodData Central or Vietnamese Food Composition Table entry
- Any run can be reproduced from its config (dataset version, prompt version, model)
- Baseline reported per slice with 95% bootstrap confidence intervals

**Artifacts:** Datacard · Baseline eval report

### M2 · Retrieval-augmented estimation

**Target:** 2026-12-20 · **Status:** ⏳ Planned

**Goal:** Ground nutrition values in food databases instead of model memory. The LLM decomposes the meal, retrieval looks up each item, code does the arithmetic.

**Scope**

- ETL for USDA FDC and the Vietnamese food table into Postgres + pgvector
- Hybrid retrieval (BM25 + embeddings, reciprocal rank fusion) with reranking
- Pipeline `decompose → retrieve → rerank → compute` behind `POST /ai/estimate`
- Ablation: baseline vs. RAG vs. RAG + rerank on the same eval set
- _Product:_ authentication, nutrition logging UI

**Exit criteria**

- Retrieval recall@5 ≥ 90% on food-name queries
- RAG pipeline improves kcal MdAPE over baseline on every slice
- Schema validity stays at 100%

**Artifacts:** Retrieval eval · Ablation report

### M3 · Observability & model gateway

**Target:** 2027-01-03 · **Status:** ⏳ Planned

**Goal:** Make every AI call traceable, and keep the product working when a model provider is slow or down.

**Scope**

- Self-hosted Langfuse: per-step spans with tokens, cost, latency and prompt version
- Prompt registry; user feedback linked to traces
- Model gateway: provider abstraction, timeouts, retry with backoff, fallback chain, per-user rate limits, Redis cache, async queue for image requests
- Load testing
- _Product:_ workout logging, progression charts (e1RM, volume, PRs)

**Exit criteria**

- 100% of AI requests traced with cost and latency
- p95 latency within eval-spec targets at expected load (text ≤ 5 s, image ≤ 8 s)
- Simulated provider outage: requests still succeed through fallback

**Artifacts:** Cost & latency dashboard · Design doc: custom gateway vs. LiteLLM

### M4 · Production on AWS

**Target:** 2027-01-10 · **Status:** ⏳ Planned

**Goal:** Reproducible infrastructure and a delivery pipeline that blocks quality regressions.

**Scope**

- Multi-stage Docker images
- Terraform: VPC, ECR, ECS Fargate, ALB, RDS Postgres (pgvector), Secrets Manager, CloudWatch, AWS Budgets alarms
- GitHub Actions with OIDC: lint/test → eval gate → build → staging → manual approval → production

**Exit criteria**

- Full environment created from scratch with `terraform apply` and torn down cleanly
- A pull request that degrades eval metrics past threshold is blocked by CI
- No long-lived AWS credentials stored in CI

**Artifacts:** Architecture diagram · CI/CD pipeline documentation

### M5 · Launch & data flywheel

**Target:** 2027-01-17 · **Status:** ⏳ Planned

**Goal:** Put the product in front of real users and turn their corrections into evaluation data.

**Scope**

- Public web app on S3 + CloudFront
- Capture differences between AI estimates and user corrections → review queue → eval set v0.2
- Drift monitoring by food category
- Curated exercise cue library, every cue with a cited source (input to M6)

**Exit criteria**

- Web app publicly launched and reachable in production
- Eval set v0.2 released, including reviewed user corrections
- Cue library covers every exercise in the default plan templates

**Artifacts:** Launch notes · Eval set v0.2 datacard

### M6 · Coach agent & plan generation

**Target:** 2027-01-31 · **Status:** ⏳ Planned

**Goal:** An AI coach that gives grounded, personalized technique advice and generates safe training plans.

**Scope**

- Hand-written agent loop with tools: training history, plateau detection, volume analysis
- Technique cues personalized from user feedback via RAG over the cue library, with no ungrounded cues
- Plan generation as generator–verifier: hard constraints checked in code, quality scored by a rubric-based LLM judge
- Guardrails for injury and medical topics; red-teaming, including prompt injection

**Exit criteria**

- Tool-selection accuracy ≥ 90% on the agent eval set
- 100% of cues shown to users traceable to a library entry
- 100% of generated plans pass hard constraints
- LLM judge agrees with human labels at Cohen's κ ≥ 0.6

**Artifacts:** Agent eval report · Plan generation eval & red-team report

### M7 · Cost optimization & operations

**Target:** 2027-02-14 · **Status:** ⏳ Planned

**Goal:** Lower unit cost without losing quality, and run the system like a production service.

**Scope**

- Model × effort comparison via Batch API; prompt caching; model routing
- Shadow deployments and A/B tests behind feature flags
- CloudWatch alarms on error rate, latency and cost; runbook; incident drill with postmortem

**Exit criteria**

- Cost per scan ≤ $0.01 while meeting the ship criteria in [`eval-spec.md`](eval-spec.md)
- Every alarm tested end to end
- Postmortem published

**Artifacts:** Cost/quality Pareto curve · Runbook · Postmortem · Case study

## Definition of done (v1.0 · 2027-02-14)

v1.0 is done when every item below is true and verifiable.

**Product**

- [ ] Users get calorie and macro targets from body stats, activity level and goal
- [ ] Users log meals from a photo or free text and can correct any estimate
- [ ] Users follow a workout plan and see progression (e1RM, volume, PRs) over time

**AI quality**

- [ ] Calorie estimation meets every ship criterion in [`eval-spec.md`](eval-spec.md) on the locked test set
- [ ] Coach and plan generation meet the [M6](#m6--coach-agent--plan-generation) exit criteria
- [ ] Results published in a versioned eval report

**Production**

- [ ] Web app publicly launched on AWS, deployed through CI with an eval gate ([M4](#m4--production-on-aws))
- [ ] p95 latency and cost per scan within eval-spec targets, visible on a dashboard

**Communication**

- [ ] README case study with architecture, eval results and lessons learned
- [ ] One technical blog post and a 3-minute demo video

## Non-goals

- **Payments and subscriptions:** the 12 weeks focus on the AI system; monetization comes after v1.0.
- **App Store release** (EAS Build): after the web version has users.
- **Self-hosted model** (distilling into a small VLM served with vLLM): only if M7 finishes early.
- **Clinical nutrition advice:** PhysiqOS gives general fitness guidance, not medical advice.
