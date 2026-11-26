# Data Card: PhysiqOS golden dataset v0.1

| | |
|---|---|
| **Version** | v0.1 (git tag `data-v0.1`, pending) |
| **Status** | Draft |
| **Files** | `text_v0.1.jsonl` (75), `image_v0.1.jsonl` (30 Nutrition5k + 20 IFPRI atlas) |
| **Schema** | `scripts/dataset_schema.py` (`TextMeal`, `ImageMeal`) |
| **Validation** | `python scripts/validate_dataset.py` (strict, exit 1 on any error) |
| **Related** | [`docs/eval-spec.md`](../docs/eval-spec.md) · [`data/README.md`](README.md) |
| **Last updated** | 2026-11-26 |

## 1. Purpose

A small, versioned golden set to measure how well PhysiqOS estimates calories and macros (protein, carbs, fat) of a meal from a **text description** or a **photo**. Every prompt, model or retrieval change is scored against it, using the metrics and thresholds in `docs/eval-spec.md`.

**Intended use:** offline evaluation of the meal-estimation feature, comparison between prompt / model / RAG versions, error analysis by slice.

**Not intended for:** training or fine-tuning (too small, and training on it would leak the test set), clinical or dietary advice, or claims about accuracy on real user traffic (see §6).

## 2. Sources

| Source | Version / date | Used for | License / terms |
|---|---|---|---|
| USDA FoodData Central: Foundation | 2026-10-29 | Text labels (ingredients) | Public domain (CC0 1.0) |
| USDA FoodData Central: SR Legacy | 2018-04 | Text labels (ingredients, generic foods) | Public domain (CC0 1.0) |
| USDA FoodData Central: FNDDS (Survey) | 2024-10-31 | Text labels (mixed dishes) | Public domain (CC0 1.0) |
| Bảng thành phần thực phẩm Việt Nam (Viện Dinh dưỡng Quốc gia), FAO edition | 2007, 525 foods | Text labels (Vietnamese foods) | Copyrighted publication. Individual values are cited with the table's *Mã số* as `source_id`; the table is not redistributed |
| [Nutrition5k](https://github.com/google-research-datasets/Nutrition5k) | metadata + `rgb_test` split, downloaded 2026-11-26 | Image samples: overhead photos, weighed ingredients, nutrient values | CC BY 4.0. Images are referenced by dish ID and not committed |
| [IFPRI photographic food atlas, Thai Nguyen, Viet Nam](https://hdl.handle.net/10568/139815) (Nguyen P.H. et al., IFPRI, doi:10.2499/p15738coll2.134869) | 2021, PDF downloaded 2026-11-26 | Image samples: overhead photos of Vietnamese meals with the weight of each dish | CC BY 4.0. Photos are cropped from the PDF locally and not committed |

Raw downloads are git-ignored. Expected local paths are listed in `data/README.md`.

## 3. Composition

### 3.1 Text set: 75 prompts

| Group | Count | What it tests |
|---|---|---|
| A · single item with grams | 23 | Food lookup, raw vs. cooked |
| B · single item, household units | 17 | Portion conversion (bowl, piece, can, tbsp…) |
| C · multi-item meals | 21 | Meal decomposition, Vietnamese mixed dishes, hidden oil |
| D · hard cases | 14 | Typos, no diacritics, mixed language, brands, non-food, vague input, prompt injection |

- Language: 45 Vietnamese (60%), 29 English, 1 mixed.
- 6 samples expect the model to ask a clarifying question; 2 are non-food (label all zero).
- 157 labeled items in total. Sources: Vietnamese table 59, SR Legacy 54, FNDDS 42, Foundation 2.
- kcal (non-zero samples): median 332, range 2 to 6,500. The maximum is an intentional absurd-portion trap (`t072`, "5kg cơm").
- Split: 54 dev / 21 test.

### 3.2 Image set: 30 Nutrition5k dishes + 20 Vietnamese meals (IFPRI atlas)

**Nutrition5k**

- 30 overhead photos from the Nutrition5k `rgb_test` split, 211 ingredients in total.
- Four kcal bins with equal allocation: `[50,250)` 8 · `[250,500)` 8 · `[500,750)` 7 · `[750,∞)` 7. Median 440 kcal, range 58 to 1,051.
- Ingredient-count groups: 1–2 items 9 · 3–5 items 11 · 6+ items 10.
- Split: 22 dev / 8 test, stratified by kcal bin (2 test dishes per bin).
- Planned: ~10 self-photographed Vietnamese meals, each ingredient weighed on a kitchen scale before serving, shot from two angles (overhead and 45°).

Selection rules for the Nutrition5k subset are in `data/README.md` ("Nutrition5k subset"). The fixed list is `data/nutrition5k_selected.csv`.

**IFPRI atlas**

- 20 overhead photos of Vietnamese meals (rice, braised or fried fish and meat, stir-fried vegetables, soup), each from a **different meal** of the atlas. 4 or 5 dishes per tray.
- One portion size per meal, 5 of each: S · M · L · XL. The atlas shows each meal in four calibrated sizes; using one size per meal keeps samples independent.
- The atlas gives the cooked weight of each dish (scale accurate to 0.1 g), transcribed in `data/ifpri_atlas_selected.json`. It gives no nutrient values.
- 175 labeled items in total. kcal: median 683, range 322 to 1,318.
- Meals were picked so that no two share most of their dishes (three near-duplicate meals were swapped out). A few share a single dish, e.g. deep-fried chicken in meals 28 and 39.
- Split: 14 dev / 6 test, assigned per meal with a fixed seed and frozen in the JSON before any labeling.

## 4. Labeling process

**Text.** Labeled by one person (the project author) on 2026-11-25:
1. Split the prompt into foods and write down assumptions (cooking state, skin, oil) in `label_notes`.
2. Look up each food in USDA FDC (Foundation / SR Legacy for ingredients, FNDDS for mixed dishes) or the Vietnamese table. Foods not in any database are decomposed into ingredients with reference portions.
3. Compute the label in code: `Σ grams × per_100g / 100`. No mental arithmetic.
4. Validate with the schema: every item has `source` and `source_id`, and the label equals the item sum (±1).

**Image (Nutrition5k).** No manual labeling. Labels are the Nutrition5k dish totals; ingredients were weighed by the dataset authors. Per-ingredient values come from `ingredients_metadata.csv` (values per gram), stored as `nutrient_per_100g = value per g × 100` so text and image share one unit. `source_id` is the ingredient `id` in that file. Recorded as `labeled_by: nutrition5k`.

**Image (IFPRI atlas).** The atlas authors weighed each cooked dish; nutrient values come from USDA FDC and the Vietnamese table, looked up with `scripts/lookup.py`, and the label is computed in code. Fixed rules per dish type: cooked weights map to cooked-state entries; stir-fried dishes are weight − 6 g of food + 6 g vegetable oil unless the entry already includes frying fat; braised (kho) dishes are weight − 5 g + 5 g sugar; soups are split into broth / vegetables / meat (60 / 30 / 10% by default, other shares stated per dish); Vietnamese-table entries with no fat value take fat from a USDA analogue. Every assumption is written per dish in `label_notes`. Items live in `data/ifpri_atlas_selected.json`; `scripts/build_image_dataset.py` adds a meal to `image_v0.1.jsonl` once it has items and `labeled_by`.

**Who labeled.** Text labels: the project author. Nutrition5k: the dataset's own totals. IFPRI atlas: the database entries and dish-composition rules were chosen by Claude (an LLM), recorded as `labeled_by: claude`; weights are the atlas measurements and all arithmetic is done in code. No model output is used as a label value. Because Claude is also a model this set evaluates, report atlas results separately (filter `labeled_by`) and treat them with that caveat.

## 5. Assumptions

Portion conventions (household units, Vietnamese recipe defaults, raw vs. cooked weights, edible portion) are documented in `data/README.md` ("Portion conventions"). Samples whose portion is a guess rather than a measurement carry the tag `estimated_portion`.

## 6. Limitations and biases

- **Image dishes are US cafeteria food.** Nutrition5k plates differ from Vietnamese home meals (rice, soup, shared dishes, sauces). Image results on this set do not show accuracy on Vietnamese meals. *Mitigation:* 20 Vietnamese meals from the IFPRI atlas; self-photographed meals and real user photos (from W6) later.
- **One camera setup.** All Nutrition5k photos are overhead, with the same tray, lighting and background. Real users shoot from any angle, in any light. The `view` field is recorded so results can be split by angle once self-photographed samples exist.
- **Selection skews the kcal distribution on purpose.** Bins are equally allocated, so the set over-represents high-kcal plates compared with Nutrition5k (67% under 250 kcal). Metrics are therefore not comparable with Nutrition5k paper numbers on the full test split.
- **Almond-heavy high-kcal bins.** The two top bins had only 39 and 18 candidate dishes, many of them almond plates from the cafeteria nut bar. After swapping three, 5/30 dishes still contain almonds. Calorie-dense small portions may be over-represented.
- **Small test sets.** 21 text and 8 image test samples. Differences of a few points are within noise; every headline metric is reported with a bootstrap 95% confidence interval (eval-spec §7.4). Image results by kcal bin rest on 2 test dishes each and are indicative only.
- **Atlas weights are per dish, not per ingredient.** Oil in stir-fried and fried dishes, and the solids/broth ratio of soups, are not measured; they come from database entries for the cooked dish or from documented assumptions. Atlas labels are therefore less exact than Nutrition5k labels, even though the weights are measured.
- **Atlas photos may be in model training data.** The atlas has been public since 2021, and its authors used the photos to train a food detection model. Vision-language models may have seen them, which can make results on these 20 samples look better than on new photos. Self-photographed and real user photos are the only images known to be unseen.
- **Atlas photo quality.** Crops are about 420 × 375 px, shot in a research kitchen on a plain coloured background with a reference object. Real user photos are larger, messier and shot at varied angles.
- **Two label pipelines.** Text labels use USDA and the Vietnamese table; image labels use Nutrition5k's own ingredient table. An identical food can carry slightly different per-100 g values in the two sets.
- **Single labeler for text.** All 75 text labels come from one person. Neither re-labeling consistency nor inter-annotator agreement is measured in v0.1.
- **Text prompts were written by the author**, not collected from users. Phrasing, food choice and difficulty reflect one person's view of real usage.

## 7. Splits and test-set policy

70% dev / 30% test with a fixed seed (`42`), assigned before any model output is inspected:
- Text: stratified by group × language (`scripts/split_dataset.py`).
- Image, Nutrition5k: stratified by kcal bin (`scripts/build_image_dataset.py`). Rows already in the file keep their split on rebuild.
- Image, IFPRI atlas: per meal, frozen in `data/ifpri_atlas_selected.json` before labeling.

Day-to-day iteration uses dev only. Test is run only for release candidates, aggregate metrics only. Inspected test samples are burned and replaced (eval-spec §7.2–7.3).

## 8. Versions

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-11 | 75 text prompts, 30 Nutrition5k image samples, 20 IFPRI atlas Vietnamese meals |
