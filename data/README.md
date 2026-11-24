# Data

Evaluation datasets for PhysiqOS calorie and macro estimation. The metrics, ship criteria and split rules that use this data are defined in [`docs/eval-spec.md`](../docs/eval-spec.md).

## Files

| File               | Status                         | Description                                                                           |
| ------------------ | ------------------------------ | ------------------------------------------------------------------------------------- |
| `text_v0.1.jsonl`  | Inputs written, labels pending | 75 text prompts (groups A–D), one JSON object per line                                |
| `image_v0.1.jsonl` | Planned                        | ~40 meal images (Nutrition5k subset + self-photographed, weighed meals)               |
| `DATACARD.md`      | Planned                        | Purpose, composition, labeling process, known limitations and biases                  |
| `images/`          | Planned                        | Self-photographed images only. Nutrition5k images are referenced by ID, not committed |

## Text set composition (v0.1)

| Group                            | Count | What it tests                                                                         |
| -------------------------------- | ----- | ------------------------------------------------------------------------------------- |
| A · single item with grams       | 23    | Food lookup, raw vs. cooked                                                           |
| B · single item, household units | 17    | Portion conversion (bowl, piece, can, tbsp…)                                          |
| C · multi-item meals             | 21    | Meal decomposition, Vietnamese mixed dishes, hidden oil                               |
| D · hard cases                   | 14    | Typos, no diacritics, mixed language, brands, non-food, vague input, prompt injection |

60% of prompts are in Vietnamese.

## Sample format

```json
{
  "id": "t001",
  "input": "200g thịt ba chỉ luộc",
  "lang": "vi",
  "group": "A",
  "tags": ["single_item", "has_grams", "cooked"],
  "split": "dev",
  "expected_needs_clarification": false
}
```

Labeling adds `items` (per-item grams, nutrient values per 100 g, `source`, `source_id`), the aggregated `label`, `label_notes`, `labeled_by` and `labeled_at`. See `docs/eval-spec.md` for the full schema.

## Splits

70% dev / 30% test, stratified by group, modality and language (Vietnamese / other), fixed seed `42`, stored in each sample's `split` field. Splits are assigned before any model output is inspected. Test is used only for release candidates (see `docs/eval-spec.md` §7).

## Label sources

| Source                                                                            | Used for                      | License / terms                                                                                                                       |
| --------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| [USDA FoodData Central](https://fdc.nal.usda.gov/) (Foundation, SR Legacy, FNDDS) | Ingredients and generic foods | Public domain (CC0 1.0)                                                                                                               |
| Bảng thành phần thực phẩm Việt Nam, Viện Dinh dưỡng Quốc gia                      | Vietnamese foods and dishes   | Copyrighted publication. Only individual values are cited, with the table entry as `source_id`. The table itself is not redistributed |
| [Nutrition5k](https://github.com/google-research-datasets/Nutrition5k)            | Image set (planned)           | CC BY 4.0. Images are referenced by dish ID and downloaded by script                                                                  |

Raw database downloads are not committed. To reproduce lookups, download the sources above and record the release version and download date in `DATACARD.md`.

## Labeling rules (summary)

- Labels are computed in code from per-100 g values: `kcal = Σ grams × kcal_per_100g / 100`. No mental arithmetic.
- Every nutrient value carries a `source` and `source_id`.
- Assumptions (cooking method, skin on/off, added oil) are written in `label_notes`.
- **No LLM-generated labels.** The model under evaluation must not grade itself.
