"""Search USDA FoodData Central and the Vietnamese food table for a food, for labeling.

Prints fdcId, source, per-100 g kcal/protein/carb/fat and household portions
(`foodPortions`, e.g. "1 cup = 158 g"). With --id and --grams it prints a
ready-to-paste `items` entry for data/text_v0.1.jsonl.

Labeling helper only: it reads the databases, it never writes labels.

Usage:
    python scripts/lookup.py pork belly                 # USDA, all words must match
    python scripts/lookup.py rice white cooked -n 5
    python scripts/lookup.py --vn thit lon              # Vietnamese table, accents optional
    python scripts/lookup.py --id 168878                 # one food (USDA fdcId or VN mã số)
    python scripts/lookup.py --id 7018 --grams 150       # JSON item to paste
    python scripts/lookup.py --id 7018 --grams 150 --add t001 --note "150 g raw weight."
                                                         # append the item to row t001 directly

Databases:
- every data/FoodData_Central_*.json (USDA SR Legacy, Foundation, Survey/FNDDS;
  FNDDS has prepared and mixed dishes such as "Soup, pho, with meat")
- data/raw/vn_fct/VTN_FCT_2007.pdf (Bảng thành phần thực phẩm Việt Nam 2007,
  Viện Dinh dưỡng; parsed with `pdftotext`). Values are per 100 g EDIBLE portion.
The first run builds a small index in data/.cache/ so later searches are instant.
Raw downloads and the cache are git-ignored, see data/README.md.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA_DIR / ".cache" / "food_index.json"
VN_PDF = DATA_DIR / "raw" / "vn_fct" / "VTN_FCT_2007.pdf"

SOURCE_BY_DATATYPE = {
    "SR Legacy": "usda_sr_legacy",
    "Foundation": "usda_foundation",
    "Survey (FNDDS)": "usda_fndds",
}

# USDA nutrient numbers. Energy: 208 is "Energy (kcal)"; many Foundation foods
# only report the Atwater variants, so fall back to Specific (958), then General (957).
# Never use 268, which is Energy in kJ.
ENERGY_NUMBERS = ["208", "958", "957"]
MACRO_NUMBERS = {"protein": "203", "carb": "205", "fat": "204"}


def database_files() -> list[Path]:
    files = sorted(DATA_DIR.glob("FoodData_Central_*.json"))
    return files + ([VN_PDF] if VN_PDF.exists() else [])


# --- Vietnamese food composition table (PDF) --------------------------------

# Food names in the PDF use the legacy TCVN3 (ABC) font encoding, e.g.
# "Ng« b¾p t−¬i" = "Ngô bắp tươi". Map those glyphs back to Unicode.
_TCVN3 = dict(
    zip(
        "¸µ¶·¹¨¾»¼½Æ©ÊÇÈÉËÐÌÎÏÑªÕÒÓÔÖÝ×ØÜÞãßáâä«èåæçé¬íêëìîóïñòô­øõö÷ùýúûüþ®¡¢£¤¥¦§",
        "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĂÂÊÔƠƯĐ",
    )
)
_TCVN3.update({"−": "ư", "μ": "à"})  # how pdftotext renders the ư / à glyphs

_NUM = r"([\d.]+|-)"
_VN_PATTERNS = {
    "calories": rf"Năng lượng \(Energy ?\)\s+KCal\s+{_NUM}",
    "protein": rf"^\s*Protein\s+g\s+{_NUM}",
    "carb": rf"Glucid \(Carbohydrate\)\s+g\s+{_NUM}",
    "fat": rf"Lipid \(Fat\)\s+g\s+{_NUM}",
}


def _from_tcvn3(text: str) -> str:
    return "".join(_TCVN3.get(c, c) for c in text)


def parse_vn_pdf(path: Path) -> list[dict]:
    if shutil.which("pdftotext") is None:
        print("warning: pdftotext not installed (poppler), skipping the Vietnamese table", file=sys.stderr)
        return []
    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True
    ).stdout
    foods = []
    # One food per page; each page starts with "Tên thực phẩm (Vietnamese):" (TCVN3-encoded).
    for block in re.split(r"(?=T\S*n th\S*c ph\S*m \(Vietnamese\):)", text)[1:]:
        vn = re.search(r"\(Vietnamese\):\s+(.+?)\s{2,}STT:", block)
        en = re.search(r"\(English\):\s+(.+?)\s{2,}M\S* s\S*:\s*(\d+)", block)
        waste = re.search(r"\(%\):\s*([\d.]+)", block)
        if not (vn and en):
            continue
        per_100g = {}
        for name, pattern in _VN_PATTERNS.items():
            m = re.search(pattern, block, re.MULTILINE)
            per_100g[name] = float(m.group(1)) if m and m.group(1) != "-" else None
        name_en = en.group(1).strip(" -")
        foods.append(
            {
                "fdc_id": en.group(2),  # "Mã số" in the table
                "source": "vn_fct",
                "name": _from_tcvn3(vn.group(1).strip()),
                "name_en": name_en,
                "waste_pct": float(waste.group(1)) if waste else None,
                "per_100g": per_100g,
                "portions": [],
            }
        )
    return foods


def fold(text: str) -> str:
    """Lowercase and strip Vietnamese accents, so "thit lon" matches "Thịt lợn"."""
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def extract(food: dict) -> dict:
    by_number = {
        n["nutrient"].get("number"): n.get("amount")
        for n in food.get("foodNutrients", [])
        if n.get("amount") is not None
    }
    calories = next((by_number[k] for k in ENERGY_NUMBERS if k in by_number), None)
    portions = []
    for p in food.get("foodPortions", []):
        if not p.get("gramWeight"):  # FNDDS "Quantity not specified" rows have 0 g
            continue
        if p.get("portionDescription"):  # FNDDS: "1 cup", "1 bowl"; its modifier is a code
            portions.append({"portion": p["portionDescription"], "grams": p["gramWeight"]})
            continue
        unit = p.get("measureUnit", {}).get("name", "")
        unit = "" if unit == "undetermined" else unit
        label = " ".join(str(x) for x in (p.get("amount") or p.get("value", ""), unit, p.get("modifier", "")) if x)
        portions.append({"portion": label.strip(), "grams": p.get("gramWeight")})
    return {
        "fdc_id": str(food["fdcId"]),
        "source": SOURCE_BY_DATATYPE.get(food.get("dataType"), food.get("dataType")),
        "name": food["description"],
        "per_100g": {
            "calories": calories,
            **{name: by_number.get(num) for name, num in MACRO_NUMBERS.items()},
        },
        "portions": portions,
    }


def load_index() -> list[dict]:
    files = database_files()
    if not files:
        sys.exit(f"No FoodData_Central_*.json in {DATA_DIR}. Download them first (see data/README.md).")
    signature = [[f.name, f.stat().st_mtime] for f in files]

    if CACHE.exists():
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        if cached.get("signature") == signature:
            return cached["foods"]

    print("Building index (first run only)...", file=sys.stderr)
    foods = []
    for f in files:
        if f.suffix == ".pdf":
            foods.extend(parse_vn_pdf(f))
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for records in data.values():  # top-level key differs per download
            foods.extend(extract(food) for food in records)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps({"signature": signature, "foods": foods}, ensure_ascii=False), encoding="utf-8")
    return foods


def fmt(value) -> str:
    return "—" if value is None else f"{value:g}"


def print_food(food: dict, with_portions: bool) -> None:
    n = food["per_100g"]
    print(
        f"{food['fdc_id']:>7}  {food['source']:<16} "
        f"kcal {fmt(n['calories']):>5} · P {fmt(n['protein']):>5} · C {fmt(n['carb']):>5} · F {fmt(n['fat']):>5}  "
        f"{food['name']}" + (f"  ({food['name_en']})" if food.get("name_en") else "")
    )
    if food.get("waste_pct"):
        print(f"{'':>9}↳ thải bỏ {food['waste_pct']:g}%: values are per 100 g edible part")
    if with_portions:
        for p in food["portions"]:
            print(f"{'':>9}↳ {p['portion']} = {p['grams']:g} g")


def add_item(dataset: Path, sample_id: str, item: dict, note: str | None) -> None:
    """Append `item` to the `items` of row `sample_id` in the JSONL, in place.

    Only copies the looked-up item into the row; the label itself is still
    computed by fill_labels.py. Other lines are written back unchanged.
    """
    lines = dataset.read_text(encoding="utf-8").splitlines()
    for lineno, raw in enumerate(lines, start=1):
        if f'"{sample_id}"' not in raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as e:
            sys.exit(f"{dataset}:{lineno}: invalid JSON at column {e.colno} ({e.msg}), fix that line first")
        if row.get("id") != sample_id:
            continue
        row.setdefault("items", []).append(item)
        if note:
            old = row.get("label_notes")
            row["label_notes"] = f"{old} {note}" if old else note
        stale = "label" in row
        lines[lineno - 1] = json.dumps(row, ensure_ascii=False)
        dataset.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"added to {sample_id} (line {lineno}), now {len(row['items'])} item(s)", file=sys.stderr)
        if stale:
            print("note: this row already has a label, run fill_labels.py --write --recompute", file=sys.stderr)
        return
    sys.exit(f"id {sample_id} not found in {dataset}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("words", nargs="*", help="search words (all must match)")
    parser.add_argument("--vn", action="store_true", help="search the Vietnamese table instead of USDA")
    parser.add_argument("--id", help="show one food by USDA fdcId or VN mã số")
    parser.add_argument("--grams", type=float, help="with --id: print a JSON item for this weight")
    parser.add_argument("-n", type=int, default=15, help="max results (default 15)")
    parser.add_argument("-p", "--portions", action="store_true", help="also list household portions")
    parser.add_argument("--add", metavar="SAMPLE_ID", help="with --id/--grams: append the item to this row (e.g. t001)")
    parser.add_argument("--note", help="with --add: text to add to label_notes")
    parser.add_argument("--dataset", type=Path, default=DATA_DIR / "text_v0.1.jsonl", help="JSONL for --add")
    args = parser.parse_args()
    if args.add and (args.id is None or args.grams is None):
        parser.error("--add needs --id and --grams")

    foods = load_index()

    if args.id:
        food = next((f for f in foods if f["fdc_id"] == args.id), None)
        if food is None:
            sys.exit(f"id {args.id} not found")
        if args.grams is None:
            print_food(food, with_portions=True)
            return
        missing = [k for k, v in food["per_100g"].items() if v is None]
        if missing:
            print(f"warning: missing {', '.join(missing)}, fill them from another source", file=sys.stderr)
        # "Carbohydrate, by difference" can come out slightly negative in Foundation data.
        negative = [k for k, v in food["per_100g"].items() if v is not None and v < 0]
        if negative:
            print(
                f"warning: negative {', '.join(negative)} in USDA data; the schema rejects < 0, "
                "set it to 0 and say so in label_notes",
                file=sys.stderr,
            )
        if food["source"] == "vn_fct" and "cồn" in food["name"]:
            print(
                "warning: the Vietnamese table leaves alcohol out of kcal (beer 11 kcal/100 g). "
                "Use USDA for alcoholic drinks",
                file=sys.stderr,
            )
        if food.get("waste_pct"):
            print(
                f"warning: per 100 g edible part ({food['waste_pct']:g}% waste); "
                "--grams must be the edible weight",
                file=sys.stderr,
            )
        item = {
            "weight": args.grams,
            "food_name": food["name"],
            "nutrient_per_100g": food["per_100g"],
            "source": food["source"],
            "source_id": food["fdc_id"],
        }
        print(json.dumps(item, ensure_ascii=False))
        if args.add:
            add_item(args.dataset, args.add, item, args.note)
        return

    if not args.words:
        parser.error("give search words or --id")
    # Whole-word prefix match: "cooked" must not match "uncooked", but "egg" matches "eggs".
    # --vn matches the Vietnamese and English name, accents optional.
    patterns = [re.compile(rf"\b{re.escape(fold(w))}") for w in args.words]
    pool = [f for f in foods if (f["source"] == "vn_fct") == args.vn]
    hits = [
        f for f in pool if all(p.search(fold(f["name"] + " " + f.get("name_en", ""))) for p in patterns)
    ]
    hits.sort(key=lambda f: len(f["name"]))  # shorter names are usually the generic food
    for food in hits[: args.n]:
        print_food(food, with_portions=args.portions)
    print(f"\n{len(hits)} match(es)" + (f", showing {args.n}" if len(hits) > args.n else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
