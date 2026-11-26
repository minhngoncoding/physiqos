# Eval Spec: Meal Calorie Estimation (v0.1)

| | |
|---|---|
| **Status** | Draft v0.1 |
| **Owner** | @minhngoncoding |
| **Last updated** | 2026-11-26 |
| **Related** | [`docs/ROADMAP.md`](ROADMAP.md) · `data/DATACARD.md` (W1) · eval harness (W2) |

> Values marked **(proposed)** are initial choices to be validated against the W2 baseline. Any change to a threshold must be recorded in the [Changelog](#11-changelog) with a reason.

---

## 1. Summary

PhysiqOS estimates the calories and macros of a meal from a **photo**, a **text description**, or **both**. This document defines what a "correct" estimate means, how we measure it, and the quality bar required before the feature ships. Every prompt, model, or retrieval change is evaluated against this spec on a versioned golden dataset.

## 2. Scope

**In scope (v0.1)**
- Calorie and macro (protein / carbs / fat) estimation for a single meal.
- Food-item detection: which foods are in the meal, and how much of each.
- Handling non-food input and ambiguous input.
- Operational targets: latency and cost per request.

**Out of scope (tracked in [§9](#9-future-work))**
- Workout plan generation and coaching cues (W9–W10).
- Medical / safety guardrails for the coach (W10).
- Personalization from user history.

## 3. Task definition

### 3.1 Input

| Modality | Example |
|---|---|
| Text | `"250g ức gà luộc, không da"`, `"1 tô phở bò tái lớn"` |
| Image | Photo of a meal, top-down or ~45° |
| Image + note | Photo plus `"phần cơm khoảng 1 chén"` |

### 3.2 Output

One JSON object per meal:

```json
{
  "is_food": true,
  "needs_clarification": false,
  "clarification_question": null,
  "confidence": 0.82,
  "items": [
    {
      "name": "chicken breast, boiled, skinless",
      "name_vi": "ức gà luộc, không da",
      "grams": 250,
      "kcal": 413,
      "protein_g": 77.5,
      "carbs_g": 0.0,
      "fat_g": 8.9,
      "confidence": 0.9
    }
  ],
  "total": { "kcal": 413, "protein_g": 77.5, "carbs_g": 0.0, "fat_g": 8.9 }
}
```

| Field | Meaning |
|---|---|
| `is_food` | `false` for non-food input. Then `items` is empty and `total` is all zeros. Distinguishes "not food" from genuinely ~0 kcal foods (water, black coffee). |
| `needs_clarification` | `true` when the input is too ambiguous to estimate responsibly. `clarification_question` holds the question for the user. |
| `confidence` | Meal-level score in [0, 1]. Per-item `confidence` is optional in v0.1. |
| `items[].grams` | Estimated portion size. **Required**: it separates *wrong food* errors from *wrong portion* errors, and the RAG pipeline (W3–W4) depends on it. |
| `total` | Sum of items. Must equal the item sum within rounding (validated by the harness). |

## 4. Dataset

Full details live in `data/DATACARD.md`. Summary:

| Set | Size | Composition |
|---|---|---|
| Text | 75 | **A** single item with grams (23) · **B** single item, household units (17) · **C** multi-item meals (21) · **D** hard cases: typos, mixed language, non-food, vague (14). ≥ 60% Vietnamese. |
| Image | 50 | 30 Nutrition5k dishes (stratified by kcal range) + 20 Vietnamese meals from the IFPRI photographic food atlas (dish weights measured by the atlas authors; one portion size per meal). Self-photographed meals later |

**Ground truth.** Text labels come from USDA FoodData Central and the Vietnamese Food Composition Table, computed as `Σ grams × per_100g / 100` in code. Nutrition5k image labels are the dataset's own totals (ingredients weighed by its authors), with per-ingredient values converted from per gram to per 100 g. IFPRI atlas meals use the dish weights from the atlas and are labeled like text samples (database lookup per dish). Self-photographed meals are weighed on a kitchen scale and labeled the same way. Every value records its source and food ID. **No LLM output is used as a label value.** For the IFPRI atlas meals, the database entries and composition rules were chosen by Claude (`labeled_by: claude`), so those results are reported separately.

**Required edge cases** (to exercise §5.1 and §5.4): near-zero-kcal items (iced tea, black coffee, broth), items with a zero macro (e.g. 0 g carbs), and non-food inputs.

## 5. Metrics

### 5.1 Calorie accuracy (primary)

For a sample with true total `y` and predicted total `ŷ`:

- **Absolute percentage error:** `APE = |ŷ − y| / y`
- **Pass rule (low-kcal safe):** a sample passes if `|ŷ − y| ≤ max(τ · y, 30 kcal)`, where `τ` is the slice tolerance from §6. **(proposed)**
  The 30 kcal floor prevents near-zero items from dominating the metric. Estimating 15 kcal for a 5 kcal coffee is a 200% APE but irrelevant to the user.

| Metric | Definition | Role |
|---|---|---|
| **MdAPE** | Median APE over samples with `y ≥ 50 kcal` | **Primary.** Robust to outliers |
| Pass rate | % of samples passing the pass rule (all samples) | Primary, paired with MdAPE |
| MAPE | Mean APE over samples with `y ≥ 50 kcal` | Reported for comparison; sensitive to outliers |

### 5.2 Bias

- **Mean signed percentage error:** `MSPE = mean((ŷ − y) / y)` over samples with `y ≥ 50 kcal`.
- Target: **|MSPE| ≤ 5%** **(proposed)**.

Rationale: a user on a ~375 kcal/day deficit eating ~2,000 kcal/day loses a quarter of the deficit to a 5% systematic under-estimate. Random errors partially cancel across meals; **systematic bias accumulates**, which is why bias has its own threshold.

### 5.3 Macro accuracy

Macros are measured in **absolute grams** (MAE), not percentages, because zero-macro items (0 g carbs in chicken breast) make percentage error undefined.

| Metric | Target (text A) | Target (other slices) |
|---|---|---|
| Protein MAE | ≤ 5 g | ≤ 10 g **(proposed)** |
| Carbs MAE | ≤ 8 g | ≤ 15 g **(proposed)** |
| Fat MAE | ≤ 5 g | ≤ 10 g **(proposed)** |

Protein is the most important macro for the target users (resistance training, fat loss).

### 5.4 Item detection

A predicted item **matches** a gold item if both map to the same canonical food (gold labels carry `aliases`, e.g. `ức gà` ↔ `chicken breast`). Unresolved pairs are adjudicated manually during error analysis.

| Metric | Text | Image |
|---|---|---|
| **Precision**: predicted items that are real | ≥ 90% | ≥ 75% **(proposed)** |
| **Recall**: real items that were found | ≥ 90% | ≥ 75% **(proposed)** |

### 5.5 Input handling

| Metric | Target |
|---|---|
| Non-food detection: `is_food = false` on non-food samples | **100%** (hard constraint) |
| No false rejections: `is_food = true` on food samples | **100%** (hard constraint) |
| Clarification recall: flags samples labelled `expected_needs_clarification` | ≥ 80% **(proposed)** |
| Clarification rate on clear inputs (groups A, B) | ≤ 10%, so the model doesn't over-ask |
| Schema validity | **100%** (hard constraint) |

### 5.6 Confidence calibration

Bucket samples by `confidence` (e.g. [0–0.5), [0.5–0.8), [0.8–1]) and report the pass rate per bucket. Higher-confidence buckets should have higher pass rates. **Reported only in v0.1, no threshold**; a threshold is set once the baseline shows the shape.

### 5.7 Operational

**Latency** (end-to-end API time, measured by the harness):

| Feature | p50 | p95 |
|---|---|---|
| Estimate from text | ≤ 3 s | ≤ 5 s |
| Estimate from image | ≤ 5 s | ≤ 8 s |
| Coach chat: time to first token (W9) | ≤ 1.5 s | ≤ 3 s |

**Cost per request.** Budget derived from unit economics:
- Pro at ~US$4.99/month, minus ~15% store fee, nets ~US$4.2.
- AI cost should stay ≤ 20–30% of revenue, i.e. ≤ ~US$1/user/month.
- At ~90 scans/month plus some coach usage, that gives **≤ US$0.01 per scan**.
- The free tier (3 scans/day) must be cheaper still.

Initial estimates (≈1,500 image + 1,000 prompt input tokens, ≈500 output tokens, thinking excluded). **To be replaced with measured `usage` in W2.**

| Model | Price in / out (per 1M tokens) | Est. cost / scan | 90 scans / month |
|---|---|---|---|
| Claude Opus 5.5 | $4 / $20 | ~$0.02 | ~$2–3.5 ❌ |
| Claude Sonnet 5.5 | $2 / $10 | ~$0.01 | ~$1 ⚠️ |
| Claude Haiku 5.5 | $0.10 / $0.50 | ~$0.0005 | ~$0.05 ✅ |

## 6. Ship criteria

A release candidate ships only if **all** of the following hold on the **test split**.

**Per-slice calorie accuracy:**

| Slice | Tolerance `τ` | MdAPE ≤ | Pass rate ≥ |
|---|---|---|---|
| Text A: single item with grams | 10% | 10% | 80% **(proposed)** |
| Text B: household units | 15% | 15% **(proposed)** | 70% **(proposed)** |
| Text C: multi-item meals | 20% | 20% **(proposed)** | 65% **(proposed)** |
| Text D: hard cases (food only) | 25% | 25% **(proposed)** | 60% **(proposed)** |
| Image + note, single dish | 15% | 15% | 70% **(proposed)** |
| Image, single dish | 20% | 20% | 65% **(proposed)** |
| Image, multi-dish | 25% | 25% (owner range: 20–30%) | 60% **(proposed)** |

**Global criteria:**
- |MSPE| ≤ 5% overall (§5.2).
- Macro MAE targets met (§5.3).
- All hard constraints met: non-food detection, no false rejections, schema validity (§5.5).
- Latency p95 and cost per scan within §5.7 budgets.
- **Human baseline:** MdAPE must beat the owner's own eyeball estimates on the same 20 samples, recorded *before* looking at the labels. This turns "better than guessing by eye" into a measurable bar.

## 7. Evaluation protocol

### 7.1 Splits
- **70% dev / 30% test**, fixed random seed (`42`), stored in each sample's `split` field. Stratified per modality:
  - **Text:** by `group` (A–D) × language (Vietnamese / other).
  - **Image:** Nutrition5k by kcal bin (image samples have no group or language); IFPRI atlas per meal (one photo per meal, no two meals sharing most of their dishes). Rows already split keep their split when the file is rebuilt.
- Splits are created **before** any model output is inspected.

### 7.2 Using the test set
- Day-to-day prompt and model iteration runs on **dev only**.
- Test is run **only for release candidates** (e.g. end of W2 baseline, end of W4 RAG). Each test run is logged with date, git SHA, prompt version, model, and reason.
- From a test run, read **aggregate metrics only**. Do not inspect individual test failures to tune prompts.

### 7.3 Leakage policy
If test samples are inspected or used for tuning, they are **burned**: moved to dev, and replaced with fresh samples. From W8, replacements come from real user corrections.

### 7.4 Statistical caveat
With ~30 test samples, differences of a few points are within noise. Every headline metric is reported with a **bootstrap 95% confidence interval**. A change counts as an improvement only when the intervals support it.

## 8. Ambiguity policy

How ambiguous portions are labelled in the golden set, so that scoring is deterministic:

- **Reference portions.** Unquantified items use a documented Vietnamese reference portion. Example: `1 tô phở` uses the standard serving from the Vietnamese Food Composition Table or a measured reference. The source goes in `label_notes`.
- **Size modifiers.** `nhỏ / vừa / lớn` scale the reference portion by **0.75 / 1.0 / 1.3** **(proposed)**. "Large" maps toward the upper bound and "small" toward the lower bound.
- **Regional default.** Portions default to Vietnamese norms. "Một tô phở" in Vietnam is not a US serving.
- **When to ask instead of assume.** If no reasonable reference portion exists, or the item is unidentifiable, the expected output is `needs_clarification = true`.
- **Personalization is out of eval scope.** Using a user's history (e.g. "their usual bowl") is a product feature. Golden-set scoring must not depend on user history.

## 9. Future work

| Area | Planned eval | Week |
|---|---|---|
| Workout plan generation | Hard-constraint checks in code (equipment, injuries, 10–20 sets per muscle group per week) + LLM-as-judge rubric calibrated against owner labels | W10 |
| Coaching cues | Faithfulness: every cue must exist in the curated cue library, no invented cues. Correct cue for exercise and fault. | W9 |
| Coach safety | Red-team set: pain or injury mentions must trigger "stop and see a professional" | W10 |
| Personalization | Portion priors from user history | post-v1 |

## 10. Open questions

- [ ] Are the 0.75 / 1.0 / 1.3 size multipliers realistic for Vietnamese dishes? Validate with ~5 weighed meals.
- [ ] Is a 30 kcal floor right for the pass rule, or should it scale with meal size?
- [ ] Should per-item confidence become required once calibration data exists?
- [ ] Revisit all **(proposed)** thresholds after the W2 baseline.

## 11. Changelog

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-11-23 | Initial draft |
| v0.1 | 2026-11-26 | §4: ground truth also covers Nutrition5k image labels (dataset totals, per g × 100) and self-photographed meals. §7.1: split stratified per modality: text by group × language, image by kcal bin, because image samples have no group or language. No threshold changed. |
| v0.1 | 2026-11-26 | §4: image set is 30 Nutrition5k + 20 IFPRI atlas Vietnamese meals (was ~30 + ~10 self-photographed). §7.1: atlas split per meal. No threshold changed. |
| v0.1 | 2026-11-26 | §4: IFPRI atlas labels: database entries chosen by Claude, values computed in code from atlas weights; reported separately. No threshold changed. |
