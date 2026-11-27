# PhysiqOS Roadmap

> **Last updated:** 2026-11-27 · **Current milestone:** M1 Evaluation foundation

PhysiqOS is developed as a production LLM system. Every milestone has measurable exit criteria and ships a written artifact (report, design doc or dashboard), linked here once complete. Changes to prompts, models or retrieval are evaluated against the golden set defined in [`eval-spec.md`](eval-spec.md) before merge.

The plan follows a "production early" order: tracing from the first eval run, a minimal AWS deployment with a CI eval gate right after the first real pipeline, and a first tool-using agent before the public launch. Every later feature is built, measured and shipped on the production stack.

**Status:** ✅ Done · 🚧 In progress · ⏳ Planned

## Overview

| Milestone                                                                        | Target date | Status | Key deliverable                               |
| -------------------------------------------------------------------------------- | ----------- | ------ | --------------------------------------------- |
| [M1 · Evaluation foundation](#m1--evaluation-foundation)                         | 2026-12-06  | 🚧     | Baseline eval report                          |
| [M2 · Retrieval-augmented estimation](#m2--retrieval-augmented-estimation)       | 2026-12-15  | ⏳     | Ablation report                               |
| [M3 · Production on AWS](#m3--production-on-aws)                                 | 2026-12-20  | ⏳     | Architecture diagram, CI with eval gate       |
| [M4 · Tool-calling agent v0](#m4--tool-calling-agent-v0)                         | 2026-12-27  | ⏳     | Agent eval v0, hand-written vs. LangGraph     |
| [M5 · Launch & data flywheel](#m5--launch--data-flywheel)                        | 2027-01-03  | ⏳     | Public web app, eval set v0.2                 |
| [M6 · Coach agent & plan generation](#m6--coach-agent--plan-generation)          | 2027-01-17  | ⏳     | Agent eval & red-team report                  |
| [M7 · Model gateway & cost optimization](#m7--model-gateway--cost-optimization)  | 2027-01-24  | ⏳     | Cost & latency dashboard, Pareto curve        |
| [M8 · Operations & v1.0](#m8--operations--v10)                                   | 2027-01-31  | ⏳     | Runbook, postmortem, case study               |
| [Stretch · Self-hosted distilled model](#stretch--self-hosted-distilled-model)   | 2027-02-14  | ⏳     | Distillation & serving report                 |

## Milestones

### M1 · Evaluation foundation

**Target:** 2026-12-06 · **Status:** 🚧 In progress

**Goal:** Build a versioned golden dataset and a reproducible, traced eval harness before any pipeline, so every later change is measured rather than eyeballed.

**Scope**

- Eval spec: task definition, metrics, ship criteria ([`eval-spec.md`](eval-spec.md))
- Golden dataset v0.1: 75 labeled text prompts, 50 labeled images (30 from [Nutrition5k](https://github.com/google-research-datasets/Nutrition5k), 20 Vietnamese meals from the [IFPRI photographic food atlas, Thai Nguyen](https://hdl.handle.net/10568/139815)), [datacard](../data/DATACARD.md)
- Eval harness: config-driven runs, per-run artifacts, unit-tested metrics
- Langfuse tracing from the first run: per-call spans with tokens, cost, latency, prompt version and run id
- Zero-shot baseline with structured output, followed by error analysis
- _Product:_ backend skeleton, calorie and macro target calculator (TDEE)

**Exit criteria**

- Dataset v0.1 tagged; every label traceable to a USDA FoodData Central or Vietnamese Food Composition Table entry
- Any run can be reproduced from its config (dataset version, prompt version, model)
- Every model call in an eval run is visible as a trace linked to its run id
- Baseline reported per slice with 95% bootstrap confidence intervals

**Artifacts:** Datacard · Baseline eval report

### M2 · Retrieval-augmented estimation

**Target:** 2026-12-15 · **Status:** ⏳ Planned

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

### M3 · Production on AWS

**Target:** 2026-12-20 · **Status:** ⏳ Planned

**Goal:** Get the estimation pipeline running in the cloud early, behind a delivery pipeline that blocks quality regressions. Start minimal and harden in later milestones.

**Scope**

- Multi-stage Docker images pushed to ECR
- One container service on ECS Fargate or App Runner, RDS Postgres (pgvector), Secrets Manager, CloudWatch logs, AWS Budgets alarm
- GitHub Actions with OIDC: lint/test → eval gate → build → deploy

**Exit criteria**

- Environment can be recreated from scratch by following the documented setup, and torn down cleanly
- A pull request that degrades eval metrics past threshold is blocked by CI
- No long-lived AWS credentials stored in CI

**Artifacts:** Architecture diagram · CI/CD pipeline documentation

### M4 · Tool-calling agent v0

**Target:** 2026-12-27 · **Status:** ⏳ Planned

**Goal:** Turn the estimation pipeline into tools an agent can call, and measure whether it calls the right one. Build the loop by hand first, then rebuild it in LangGraph to see exactly what the framework adds.

**Scope**

- Hand-written tool loop on the Claude API: tool schemas, tool-call parsing, max steps, tool error handling
- Same agent rebuilt in LangGraph: state, `ToolNode`, checkpointer, streaming
- Tools: food search (M2 retrieval), meal logging, TDEE calculator
- Agent eval set v0 for tool selection and arguments
- Minimal rate limiting and retry with backoff, enough for the public launch in M5
- _Product:_ workout logging, progression charts (e1RM, volume, PRs)

**Exit criteria**

- Tool-selection accuracy ≥ 90% on the agent eval set v0
- Both implementations evaluated on the same set, with latency and cost per conversation
- Every agent step visible as a span in the trace

**Artifacts:** Agent eval v0 · Write-up: hand-written loop vs. LangGraph

### M5 · Launch & data flywheel

**Target:** 2027-01-03 · **Status:** ⏳ Planned

**Goal:** Put the product in front of real users and turn their corrections into evaluation data.

**Scope**

- Public web app on S3 + CloudFront
- Prompt registry; user feedback linked to traces
- Capture differences between AI estimates and user corrections → review queue → eval set v0.2
- Drift monitoring by food category
- Curated exercise cue library, every cue with a cited source (input to M6)

**Exit criteria**

- Web app publicly launched and reachable in production
- Eval set v0.2 released, including reviewed user corrections
- Cue library covers every exercise in the default plan templates

**Artifacts:** Launch notes · Eval set v0.2 datacard

### M6 · Coach agent & plan generation

**Target:** 2027-01-17 · **Status:** ⏳ Planned

**Goal:** An AI coach that gives grounded, personalized technique advice and generates safe training plans.

**Scope**

- Extend the M4 agent with training tools: training history, plateau detection, volume analysis
- Technique cues personalized from user feedback via RAG over the cue library, with no ungrounded cues
- Plan generation as generator–verifier: hard constraints checked in code, quality scored by a rubric-based LLM judge
- Guardrails for injury and medical topics; red-teaming, including prompt injection

**Exit criteria**

- Tool-selection accuracy stays ≥ 90% on the agent eval set with the new tools
- 100% of cues shown to users traceable to a library entry
- 100% of generated plans pass hard constraints
- LLM judge agrees with human labels at Cohen's κ ≥ 0.6

**Artifacts:** Agent eval report · Plan generation eval & red-team report

### M7 · Model gateway & cost optimization

**Target:** 2027-01-24 (gateway and load testing by 2027-01-10) · **Status:** ⏳ Planned

**Goal:** Keep the product working when a model provider is slow or down, know the system's cost and latency under load, then lower unit cost without losing quality.

**Scope**

- Model gateway: provider abstraction, multi-provider fallback chain, timeouts, retry with backoff, per-user rate limits, Redis cache, async queue for image requests
- Cost and latency dashboard built on the Langfuse traces from M1
- Load testing against the deployed stack
- Staging environment and manual approval step before production
- Cost: model routing, prompt caching, model × effort comparison via Batch API (or a small LoRA experiment in its place)

**Exit criteria**

- 100% of AI requests traced with cost and latency
- p95 latency within eval-spec targets at expected load (text ≤ 5 s, image ≤ 8 s)
- Simulated provider outage: requests still succeed through fallback
- Cost per scan ≤ $0.01 while meeting the ship criteria in [`eval-spec.md`](eval-spec.md)

**Artifacts:** Cost & latency dashboard · Design doc: custom gateway vs. LiteLLM · Cost/quality Pareto curve

### M8 · Operations & v1.0

**Target:** 2027-01-31 · **Status:** ⏳ Planned

**Goal:** Run the system like a production service and publish the results.

**Scope**

- Shadow deployments and A/B tests behind feature flags
- CloudWatch alarms on error rate, latency and cost; runbook; incident drill with postmortem
- README case study, technical blog post, 3-minute demo video

**Exit criteria**

- Every alarm tested end to end
- Postmortem published
- Every item in the v1.0 definition of done below is checked

**Artifacts:** Runbook · Postmortem · Case study

### Stretch · Self-hosted distilled model

**Target:** 2027-02-14 · **Status:** ⏳ Planned (only after v1.0)

**Goal:** Learn the fine-tuning and self-hosting path end to end, and compare it with the API pipeline on the same eval set.

**Scope**

- Distill the API pipeline's outputs into a small open VLM (LoRA/QLoRA)
- Serve it with vLLM; measure throughput, TTFT and cost per scan
- Route a share of traffic to it behind the gateway and compare quality

**Artifacts:** Distillation & serving report

## Definition of done (v1.0 · 2027-01-31)

v1.0 is done when every item below is true and verifiable.

**Product**

- [ ] Users get calorie and macro targets from body stats, activity level and goal
- [ ] Users log meals from a photo or free text and can correct any estimate
- [ ] Users follow a workout plan and see progression (e1RM, volume, PRs) over time

**AI quality**

- [ ] Calorie estimation meets every ship criterion in [`eval-spec.md`](eval-spec.md) on the locked test set
- [ ] Agent and plan generation meet the [M4](#m4--tool-calling-agent-v0) and [M6](#m6--coach-agent--plan-generation) exit criteria
- [ ] Results published in a versioned eval report

**Production**

- [ ] Web app publicly launched on AWS, deployed through CI with an eval gate ([M3](#m3--production-on-aws))
- [ ] p95 latency and cost per scan within eval-spec targets, visible on a dashboard

**Communication**

- [ ] README case study with architecture, eval results and lessons learned
- [ ] One technical blog post and a 3-minute demo video

## Non-goals

- **Payments and subscriptions:** the 12 weeks focus on the AI system; monetization comes after v1.0.
- **App Store release** (EAS Build): after the web version has users.
- **Clinical nutrition advice:** PhysiqOS gives general fitness guidance, not medical advice.
