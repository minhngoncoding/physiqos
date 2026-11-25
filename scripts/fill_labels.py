"""Compute `label` from `items` for rows that have items but no label yet.

label.<nutrient> = Σ weight × nutrient_per_100g.<nutrient> / 100, rounded to
2 decimals (week-01 spec §5.4: labels are computed in code, never by hand).
Also fills `labeled_by` / `labeled_at` when missing.

Rows that already have a label are left untouched unless --recompute is given.
A row with `expected_needs_clarification: true` and `items: []` gets an all-zero
label. Rows without an `items` key are not labeled yet and are skipped.

Usage:
    python scripts/fill_labels.py                 # dry run: show what would change
    python scripts/fill_labels.py --write         # update data/text_v0.1.jsonl in place
    python scripts/fill_labels.py --write --recompute   # also redo existing labels

Run scripts/validate_dataset.py --labeled-only afterwards.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

NUTRIENTS = ["calories", "protein", "carb", "fat"]


def compute_label(items: list[dict]) -> dict:
    totals = {name: 0.0 for name in NUTRIENTS}
    for item in items:
        for name in NUTRIENTS:
            totals[name] += item["weight"] * item["nutrient_per_100g"][name] / 100
    return {name: round(value, 2) for name, value in totals.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path, nargs="?", default=Path("data/text_v0.1.jsonl"))
    parser.add_argument("--write", action="store_true", help="overwrite the file in place")
    parser.add_argument("--recompute", action="store_true", help="also recompute rows that already have a label")
    parser.add_argument("--by", default="minhngon", help="value for labeled_by (default: minhngon)")
    args = parser.parse_args()

    lines = args.path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    changed = problems = 0
    today = date.today().isoformat()

    for lineno, raw in enumerate(lines, start=1):
        if not raw.strip():
            out.append(raw)
            continue
        row = json.loads(raw)

        if "items" not in row or ("label" in row and not args.recompute):
            out.append(raw)
            continue

        try:
            label = compute_label(row["items"])
        except (KeyError, TypeError) as e:
            # Incomplete item (missing weight / nutrient); leave the row for the validator to report.
            print(f"line {lineno} [{row.get('id', '?')}]: cannot compute label, missing {e}", file=sys.stderr)
            problems += 1
            out.append(raw)
            continue

        old = row.get("label")
        row["label"] = label
        row.setdefault("labeled_by", args.by)
        row.setdefault("labeled_at", today)
        if old != label:
            changed += 1
            print(f"line {lineno} [{row['id']}]: label {old} -> {label}")
        out.append(json.dumps(row, ensure_ascii=False))

    print(f"\n{changed} row(s) {'updated' if args.write else 'would change'}, {problems} skipped with problems")
    if args.write and changed:
        args.path.write_text("\n".join(out) + "\n", encoding="utf-8")
    elif changed:
        print("dry run, nothing written. Add --write to save.")


if __name__ == "__main__":
    main()
