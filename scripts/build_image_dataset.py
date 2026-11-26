"""Build data/image_v0.1.jsonl from the Nutrition5k and IFPRI atlas selections.

Nutrition5k (data/nutrition5k_selected.csv), for each selected dish:
- items: one FoodItem per ingredient. Grams come from the dish metadata,
  nutrients from ingredients_metadata.csv (cal/g, fat/carb/protein g per g),
  stored as per 100 g (× 100) so text and image samples share one unit.
  source_id is the ingredient id in ingredients_metadata.csv.
- label: the dish totals from the Nutrition5k dish metadata (ground truth).
- images: the overhead RGB image, path relative to the repo root.
- split: 70/30 dev/test stratified by kcal bin, fixed seed (same rule as
  scripts/split_dataset.py, which only handles text rows). Rows already in
  the file keep their split, so re-running never reshuffles a frozen split.

IFPRI atlas (data/ifpri_atlas_selected.json), for each selected meal photo:
- The atlas gives the cooked weight of each dish on the tray, not nutrients.
  `items` are filled in by hand in the JSON (lookup.py entries for each dish,
  or its ingredients), with `labeled_by` / `labeled_at` / `label_notes`.
- label: computed in code as Σ weight × per_100g / 100.
- split: frozen in the JSON, assigned per split_group before labeling
  (one group per meal; meals sharing most dishes would share a group).
- Entries without items yet are skipped and reported as pending.

Rows whose images are self-photographed are kept as they are.
Every row is checked with ImageMeal before anything is written.

Usage:
    uv run --project backend python scripts/build_image_dataset.py          # dry run
    uv run --project backend python scripts/build_image_dataset.py --write  # write file
"""

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from dataset_schema import ImageMeal
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nutrition5k"
SELECTED = ROOT / "data" / "nutrition5k_selected.csv"
ATLAS_SELECTED = ROOT / "data" / "ifpri_atlas_selected.json"
OUT = ROOT / "data" / "image_v0.1.jsonl"

SEED = 42
TEST_RATIO = 0.3
LABELED_AT = date(2026, 11, 26).isoformat()  # date this subset was built
LABEL_NOTES = (
    "Nutrition5k ground truth (ingredients weighed by the dataset authors). "
    "per_100g = ingredients_metadata.csv value per g × 100."
)

# Dish metadata has no header: 6 dish columns, then 7 columns per ingredient.
DISH_COLS = ["dish_id", "calories", "mass", "fat", "carb", "protein"]
INGR_COLS = ["ingr_id", "name", "grams", "calories", "fat", "carb", "protein"]


def load_dish_metadata() -> dict[str, dict]:
    dishes = {}
    for name in ("dish_metadata_cafe1.csv", "dish_metadata_cafe2.csv"):
        for line in (RAW / name).read_text().splitlines():
            parts = line.strip().split(",")
            if len(parts) < len(DISH_COLS):
                continue
            dish = dict(zip(DISH_COLS, parts))
            rest = parts[len(DISH_COLS):]
            dish["ingredients"] = [
                dict(zip(INGR_COLS, rest[i : i + len(INGR_COLS)]))
                for i in range(0, len(rest), len(INGR_COLS))
            ]
            dishes[dish["dish_id"]] = dish
    return dishes


def load_ingredients() -> dict[str, dict]:
    """Ingredient id (as in ingredients_metadata.csv, e.g. "5") -> values per gram."""
    with (RAW / "ingredients_metadata.csv").open() as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def normalize_ingr_id(ingr_id: str) -> str:
    # Dish metadata writes "ingr_0000000005", ingredients_metadata.csv writes "5".
    return str(int(ingr_id.removeprefix("ingr_")))


def per_100g(ingr: dict) -> dict:
    return {
        "calories": round(float(ingr["cal/g"]) * 100, 4),
        "protein": round(float(ingr["protein(g)"]) * 100, 4),
        "carb": round(float(ingr["carb(g)"]) * 100, 4),
        "fat": round(float(ingr["fat(g)"]) * 100, 4),
    }


def build_row(sample_id: str, sel: dict, dish: dict, ingredients: dict) -> dict:
    items = []
    for ing in dish["ingredients"]:
        grams = float(ing["grams"])
        if grams <= 0:
            continue
        ingr_id = normalize_ingr_id(ing["ingr_id"])
        items.append(
            {
                "weight": round(grams, 4),
                "food_name": ing["name"],
                "nutrient_per_100g": per_100g(ingredients[ingr_id]),
                "source": "nutrition5k",
                "source_id": ingr_id,
            }
        )
    dish_id = sel["dish_id"]
    return {
        "id": sample_id,
        "modality": "image",
        "images": [
            {
                "path": f"data/raw/nutrition5k/images/{dish_id}/rgb.png",
                "view": "overhead",
                "source": "nutrition5k",
                "dish_id": dish_id,
            }
        ],
        "items": items,
        "label": {
            "calories": round(float(dish["calories"]), 4),
            "protein": round(float(dish["protein"]), 4),
            "carb": round(float(dish["carb"]), 4),
            "fat": round(float(dish["fat"]), 4),
        },
        "split": "dev",  # placeholder, assigned below
        "tags": ["nutrition5k", f"kcal_{sel['kcal_bin']}", f"ingr_{sel['ingr_group']}"],
        "expected_needs_clarification": False,
        "label_notes": LABEL_NOTES,
        "labeled_by": "nutrition5k",
        "labeled_at": LABELED_AT,
    }


def kcal_bin(kcal: float) -> str:
    """Same bins as the Nutrition5k selection, so tags are comparable."""
    for lo, hi in [(0, 50), (50, 250), (250, 500), (500, 750)]:
        if kcal < hi:
            return f"{lo}-{hi}"
    return "750-inf"


def atlas_dish_id(entry: dict) -> str:
    return f"atlas_{entry['atlas_meal']:03d}_{entry['portion']}"


def build_atlas_row(sample_id: str, entry: dict) -> dict:
    items = entry["items"]
    label = {
        name: round(sum(i["weight"] * i["nutrient_per_100g"][name] / 100 for i in items), 4)
        for name in ("calories", "protein", "carb", "fat")
    }
    return {
        "id": sample_id,
        "modality": "image",
        "images": [
            {
                "path": entry["image"],
                "view": "overhead",
                "source": "ifpri_atlas",
                "dish_id": atlas_dish_id(entry),
            }
        ],
        "items": items,
        "label": label,
        "split": entry["split"],
        "tags": [
            "ifpri_atlas",
            f"kcal_{kcal_bin(label['calories'])}",
            f"portion_{entry['portion']}",
            f"atlas_meal_{entry['atlas_meal']:03d}",
        ],
        "expected_needs_clarification": False,
        "label_notes": entry["label_notes"],
        "labeled_by": entry["labeled_by"],
        "labeled_at": entry["labeled_at"],
    }


def assign_splits(rows: list[dict], frozen: dict[str, str]) -> None:
    strata: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        kcal_tag = next(t for t in row["tags"] if t.startswith("kcal_"))
        strata[kcal_tag].append(row)
    for key in sorted(strata):
        members = sorted(strata[key], key=lambda r: r["id"])
        rng = random.Random(f"{SEED}-image-{key}")
        rng.shuffle(members)
        n_test = round(len(members) * TEST_RATIO)
        for i, row in enumerate(members):
            row["split"] = "test" if i < n_test else "dev"
    for row in rows:  # rows already in the file keep their split
        if row["images"][0]["dish_id"] in frozen:
            row["split"] = frozen[row["images"][0]["dish_id"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="write data/image_v0.1.jsonl")
    args = parser.parse_args()

    existing = []
    if OUT.exists():
        existing = [json.loads(x) for x in OUT.read_text(encoding="utf-8").splitlines() if x.strip()]
    self_rows = [r for r in existing if any(i["source"] == "self" for i in r["images"])]
    frozen = {
        r["images"][0]["dish_id"]: r["split"]
        for r in existing
        if r["images"][0]["source"] == "nutrition5k"
    }
    # Keep ids stable: existing rows keep theirs, new dishes get the next free ones.
    old_ids = {
        r["images"][0]["dish_id"]: r["id"]
        for r in existing
        if r["images"][0]["source"] != "self"
    }
    used = {r["id"] for r in existing}
    next_num = max((int(i[1:]) for i in used), default=0) + 1

    dishes = load_dish_metadata()
    ingredients = load_ingredients()
    with SELECTED.open() as f:
        selected = sorted(csv.DictReader(f), key=lambda r: r["dish_id"])

    rows = []
    for sel in selected:
        sample_id = old_ids.get(sel["dish_id"])
        if sample_id is None:
            sample_id = f"i{next_num:03d}"
            next_num += 1
        rows.append(build_row(sample_id, sel, dishes[sel["dish_id"]], ingredients))
    assign_splits(rows, frozen)

    atlas_rows, pending = [], []
    atlas = json.loads(ATLAS_SELECTED.read_text(encoding="utf-8")) if ATLAS_SELECTED.exists() else []
    for entry in sorted(atlas, key=atlas_dish_id):
        if not entry["items"] or not entry["labeled_by"]:
            pending.append(atlas_dish_id(entry))
            continue
        sample_id = old_ids.get(atlas_dish_id(entry))
        if sample_id is None:
            sample_id = f"i{next_num:03d}"
            next_num += 1
        atlas_rows.append(build_atlas_row(sample_id, entry))

    all_rows = sorted(rows + atlas_rows + self_rows, key=lambda r: r["id"])
    errors = []
    for row in all_rows:
        try:
            ImageMeal.model_validate(row)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"]) or "(row)"
                errors.append(f"[{row['id']}] {loc}: {err['msg']}")
    if errors:
        print("\n".join(errors))
        sys.exit(1)

    splits = Counter((next(t for t in r["tags"] if t.startswith("kcal_")), r["split"]) for r in rows)
    print(
        f"{len(rows)} Nutrition5k + {len(atlas_rows)} IFPRI atlas + "
        f"{len(self_rows)} self-photographed rows, all valid"
    )
    if pending:
        print(f"IFPRI atlas: {len(pending)} meal(s) pending labels ({', '.join(pending[:5])}{', ...' if len(pending) > 5 else ''})")
    for kcal in sorted({k for k, _ in splits}):
        print(f"  {kcal:<14} dev {splits[(kcal, 'dev')]:>2}  test {splits[(kcal, 'test')]:>2}")

    if args.write:
        with OUT.open("w", encoding="utf-8") as f:
            for row in all_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {OUT.relative_to(ROOT)}")
    else:
        print("dry run, pass --write to write the file")


if __name__ == "__main__":
    main()
