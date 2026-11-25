# Data

Evaluation datasets for PhysiqOS calorie and macro estimation. The metrics, ship criteria and split rules that use this data are defined in [`docs/eval-spec.md`](../docs/eval-spec.md).

## Files

| File               | Status                         | Description                                                                           |
| ------------------ | ------------------------------ | ------------------------------------------------------------------------------------- |
| `text_v0.1.jsonl`  | Labeled (75/75)                | 75 text prompts (groups A–D), one JSON object per line                                |
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

Expected local paths (git-ignored), used by `scripts/lookup.py`:

- `data/FoodData_Central_*.json`: USDA FDC JSON downloads (SR Legacy, Foundation, Survey/FNDDS 2024-10-31; FNDDS from <https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_survey_food_json_2024-10-31.zip>, unzipped file renamed from `surveyDownload.json`)
- `data/raw/vn_fct/VTN_FCT_2007.pdf`: the 2007 Vietnamese table as published by FAO ([PDF](https://www.fao.org/fileadmin/templates/food_composition/documents/pdf/VTN_FCT_2007.pdf)), 525 foods. `source_id` is the table's *Mã số*. Values are per 100 g edible portion. Note: kcal for alcoholic drinks excludes alcohol (beer 11 kcal/100 g), so use USDA for those.

## Labeling rules (summary)

- Labels are computed in code from per-100 g values: `kcal = Σ grams × kcal_per_100g / 100`. No mental arithmetic.
- Every nutrient value carries a `source` and `source_id`.
- Assumptions (cooking method, skin on/off, added oil) are written in `label_notes`.
- **No LLM-generated labels.** The model under evaluation must not grade itself.

## Portion conventions (v0.1)

Household units and unstated details are resolved the same way in every sample, so that two prompts saying the same thing get the same label. When a sample uses a convention, its `label_notes` says so; samples whose portion is a guess rather than a measurement or a database portion carry the tag `estimated_portion`.

### Choosing a database entry

1. Prefer the entry whose name matches the prompt, including the cooking state ("boiled, drained", "cooked", "fried").
2. Vietnamese dishes and ingredients: the Vietnamese table first, USDA when the Vietnamese entry is missing, has an empty nutrient (e.g. *Bún* 1020 has no fat value) or does not reflect the cooking (e.g. *Đậu phụ nướng* 3027 has 6.4 g fat, too little for deep-fried tofu).
3. Unspecified variant: use the USDA "NFS" / "NS as to …" entry (not further specified) and its default portion ("Quantity not specified").
4. Always read the English name of a Vietnamese entry. *Quả trứng gà* (5045) is a fruit, not an egg; *Củ cái* (2002) is winged yam (khoai mỡ), not radish.
5. One food, one entry across the set: rice → 169757, banana → FNDDS 2709224, egg → VN 9001, cooked chicken breast → 171477, beef in noodle soups → VN 7004, brewed coffee → FNDDS 2710375.

### Weights

| Rule | Convention |
| ---- | ---------- |
| Edible portion | `weight` is always the edible part. Vietnamese entries list waste % (shell, bone, peel, cob); USDA portions are already edible |
| Raw vs. cooked | Use the weight in the state the database entry describes. Vietnamese meat entries are raw, so meat in Vietnamese dishes is given as raw edible weight |
| Volume → grams | Milk 1.031 g/ml (USDA 1 cup = 244 g); condensed milk 1.29 g/ml (1 cup = 306 g); water-based drinks ≈ 1 g/ml |
| Water, broth, ice | Counted at their database value (broth ≈ 6–7 kcal/100 g, ice 0); they matter for weight, not for calories |

### Household units

| Unit | Grams | Basis | Samples |
| ---- | ----- | ----- | ------- |
| 1 chén cơm (cooked rice) | 200 | weighed at home | t024, t045, t046, t047, t050 |
| 1 tô cơm | 400 | estimate: 2 chén | t062 |
| 1 tô cháo lớn (home) | 450 | weighed at home | t025 |
| 1 bát (noodle soup, home) | 450 | same bowl as t025 | t043, t070 |
| 1 tô (noodle soup, restaurant, size not given) | 600 | estimate | t044, t052 |
| 1 tô lớn (noodle soup, restaurant) | 700 | estimate | t042, t058 |
| 1 trứng gà | 50 large / 38 small | USDA portions, without shell | t002, t027, t047 |
| 1 trứng bác (scrambled) | 61 | USDA "large", includes milk/butter | t057 |
| 1 quả chuối (peeled) | 126 medium / 136 large | FNDDS / USDA SR portions | t028, t037, t059 |
| 1 lát bánh mì gối | 28 (white), 33 (whole wheat, toasted) | FNDDS "medium or regular slice" | t030, t057 |
| 1 ổ bánh mì Việt Nam | 82 | FNDDS "individual loaf" | t048 |
| 1 cái bánh bao | 100 | FNDDS "Bao bun, 1 item" | t029 |
| 1 lát pizza | 119 (size not given), 88 (medium pizza) | FNDDS | t031 |
| 1 medium pizza (11–12″) | 707 | FNDDS | t061 |
| 1 hamburger | 145 (regular), 175 (large patty) | FNDDS | t041, t054 |
| 1 phần khoai tây chiên (size not given) | 110 | FNDDS "Quantity not specified" | t041 |
| 1 tbsp | 14 oil, 16 peanut butter, 21 honey | FNDDS / USDA | t035, t036, t059 |
| Butter on 1 slice of bread | 7 | FNDDS "per slice of bread" | t057 |
| 1 cup | 240 coffee/water, 244 milk, 240 cooked oatmeal | FNDDS / USDA | t032, t039, t059 |
| 1 ly (glass) | 248 juice, 360 iced tea (with ice), 435 milk tea | FNDDS | t038, t052, t057, t058 |
| 1 lon (can) | 372 soda (12 fl oz), 496 energy drink (16 fl oz), 330 g beer (Vietnamese 330 ml can) | FNDDS / local can size | t033, t053, t060, t066 |
| 1 lốc sữa | 4 × 180 ml = 742 g | most common pack | t065 |
| 1 lát bacon (cooked) | 8 | FNDDS "medium slice, yield after cooking" | t040 |
| 1 miếng sườn non (with bone) | 40, of which ~18 g meat | estimate, VN waste 57% | t056 |
| 1 miếng gà KFC | thigh 109, drumstick 58 (edible) | USDA portions minus bone | t054 |
| 1 đùi gà góc tư (fried, bone removed) | 195 | FNDDS "medium leg" | t046 |
| "1 ít" (a little) condensed milk | 19 | FNDDS "Quantity not specified" | t069 |

### Recipe defaults for Vietnamese dishes

Composite dishes are split into ingredients. Unless the prompt says otherwise:

| Dish | Default composition |
| ---- | ------------------- |
| Phở bò tô lớn (700 g) | bánh phở 170 + bò loại II 120 (raw) + beef fat 8 + broth 402. Other sizes scale proportionally |
| Phở gà tô lớn (700 g) | bánh phở 170 + gà ta with skin 100 (raw, edible) + chicken fat 6 + broth 424 |
| Bún bò, per bát (450 g) | bún 130 + bò loại II 70 + fat / sa tế 6 + broth 244. Giò heo and chả not included |
| Cà phê sữa (đá) | condensed milk : coffee = 1 : 2 by volume → 28.4 g condensed milk + 44 g coffee per glass; ice 0 kcal |
| Trà đá | unsweetened green tea, ≈ 0 kcal |
| Bánh mì Việt Nam | always includes pâté 15 g (USDA liver pâté) + bơ trứng 10 g (USDA mayonnaise) |
| Cơm đĩa at a restaurant | rice 200 g + main + dipping sauce (nước mắm 10 g + sugar 5–6 g) |
| Thịt kho, sườn nướng, sườn chua ngọt | add the sugar of the marinade or sauce (5–8 g) |
| Stir-fried, fried dishes | add oil as its own item: 5–8 g per stir-fried dish, ~6 g absorbed per fried portion. Bacon and FNDDS "fried" entries already include it |
| Shared dish ("chia đôi") | compute the whole dish, then halve every item |
| Drinking session with unspecified food | beer as stated + estimated snacks for one person (lạc chao dầu 30, mực nướng 100, ba chỉ luộc 80) |

### Ambiguous prompts

- Unstated sweetener: sugar-free (black coffee, iced tea, fresh milk). Vietnamese "milk coffee" means condensed milk.
- Unstated fat level or variety: the USDA "NS as to …" entry (e.g. Greek yogurt, pizza crust).
- `expected_needs_clarification: true` with an identifiable food: a fallback label for the most likely reading is stored, so a model that answers without asking can still be scored (t063, t069, t072). With no identifiable food, `items` is empty and the label is 0 (t068, t071, t073).
- `non_food`: empty `items`, label 0 (t067, t074).
- Prompt injection (t070): the label ignores the injected instruction.

Open item: steamed sticky rice (xôi) uses USDA boiled glutinous rice (97 kcal/100 g), which is likely too low for steamed xôi. To be corrected once the raw-to-steamed yield is weighed (affects t016, t049).
