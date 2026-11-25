"""Validate a JSONL eval dataset against the schema and print its composition.

Checks every row with `dataset_schema.Meal` (types, allowed values, label =
sum of items), then file-level rules a single row cannot see (duplicate ids,
share of Vietnamese prompts), and prints distributions by group, language,
split and kcal range.

Usage (path defaults to data/text_v0.1.jsonl):
    python scripts/validate_dataset.py data/text_v0.1.jsonl                  # strict: every row must pass
    python scripts/validate_dataset.py data/text_v0.1.jsonl --labeled-only   # while labeling: skip rows without a label

Exit code 0 when everything passes, 1 otherwise (so CI can gate on it).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from dataset_schema import Meal

MIN_VI_SHARE = 0.6  # week-01 spec §5.1: at least 60% Vietnamese prompts

# Upper bounds (exclusive) of the kcal ranges. 0 is its own bucket so the
# non-food / needs-clarification samples are visible in the table.
KCAL_BUCKETS = [(200, "<200"), (500, "200–499"), (1000, "500–999")]


def kcal_bucket(kcal: float) -> str:
    if kcal == 0:
        return "0"
    for upper, name in KCAL_BUCKETS:
        if kcal < upper:
            return name
    return "≥1000"


def load_and_validate(
    path: Path, labeled_only: bool
) -> tuple[list[Meal], list[str], int, int]:
    """Return (valid samples, error messages, labeled row count, total row count)."""
    samples: list[Meal] = []
    errors: list[str] = []
    labeled = total = 0

    for lineno, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        total += 1

        try:
            row = json.loads(raw)
        except json.JSONDecodeError as e:
            errors.append(f"line {lineno}: invalid JSON ({e.msg})")
            continue

        if "label" in row:
            labeled += 1
        elif labeled_only:
            continue

        try:
            samples.append(Meal.model_validate(row))
        except ValidationError as e:
            row_id = row.get("id", "?")
            for err in e.errors():
                field = ".".join(str(part) for part in err["loc"]) or "(row)"
                errors.append(f"line {lineno} [{row_id}] {field}: {err['msg']}")

    return samples, errors, labeled, total


def check_file_level(samples: list[Meal], strict: bool) -> list[str]:
    errors: list[str] = []

    ids = Counter(s.id for s in samples)
    for sample_id, count in ids.items():
        if count > 1:
            errors.append(f"duplicate id {sample_id} ({count} rows)")

    # Language share only means something on the full set.
    if strict and samples:
        vi_share = sum(s.lang == "vi" for s in samples) / len(samples)
        if vi_share < MIN_VI_SHARE:
            errors.append(f"Vietnamese share {vi_share:.0%} < {MIN_VI_SHARE:.0%}")

    return errors


def print_table(title: str, counter: Counter, order: list[str] | None = None) -> None:
    total = sum(counter.values())
    print(f"\n{title}")
    for key in order or sorted(counter):
        n = counter.get(key, 0)
        print(f"  {key:<10} {n:>4}  {n / total:>5.0%}")


def print_distribution(samples: list[Meal]) -> None:
    if not samples:
        return
    print_table("group", Counter(s.group.value for s in samples))
    print_table("lang", Counter(s.lang for s in samples))
    print_table("split", Counter(s.split for s in samples))
    print_table(
        "kcal",
        Counter(kcal_bucket(s.label.calories) for s in samples),
        order=["0", *[name for _, name in KCAL_BUCKETS], "≥1000"],
    )
    print_table("group × split", Counter(f"{s.group.value}/{s.split}" for s in samples))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("data/text_v0.1.jsonl"),
        help="JSONL file (default: data/text_v0.1.jsonl, relative to the repo root)",
    )
    parser.add_argument(
        "--labeled-only",
        action="store_true",
        help="validate only rows that already have a label (use while labeling)",
    )
    args = parser.parse_args()

    samples, errors, labeled, total = load_and_validate(args.path, args.labeled_only)
    errors += check_file_level(samples, strict=not args.labeled_only)

    print(f"{args.path}: labeled {labeled}/{total}, valid {len(samples)}")
    print_distribution(samples)

    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for msg in errors:
            print(f"  {msg}", file=sys.stderr)
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
