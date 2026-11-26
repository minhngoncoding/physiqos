"""Validate a JSONL eval dataset against the schema and print its composition.

Each row is checked with the model for its `modality` (`TextMeal` for "text",
the default when the field is missing; `ImageMeal` for "image"): types, allowed
values, label = sum of items. Then file-level rules a single row cannot see
(duplicate ids across all given files, share of Vietnamese text prompts), and
distributions by modality, split and kcal range, plus group/language for text
and kcal bin / ingredient group / image source for images.

Usage (paths default to data/text_v0.1.jsonl and data/image_v0.1.jsonl):
    python scripts/validate_dataset.py                                       # whole golden set, strict
    python scripts/validate_dataset.py data/image_v0.1.jsonl                 # one file
    python scripts/validate_dataset.py data/text_v0.1.jsonl --labeled-only   # while labeling: skip rows without a label

Exit code 0 when everything passes, 1 otherwise (so CI can gate on it).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from dataset_schema import ImageMeal, TextMeal
from pydantic import ValidationError

Sample = TextMeal | ImageMeal
MODELS: dict[str, type[TextMeal] | type[ImageMeal]] = {
    "text": TextMeal,
    "image": ImageMeal,
}
DEFAULT_PATHS = [Path("data/text_v0.1.jsonl"), Path("data/image_v0.1.jsonl")]

MIN_VI_SHARE = 0.6  # week-01 spec §5.1: at least 60% Vietnamese text prompts

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
) -> tuple[list[Sample], list[str], int, int]:
    """Return (valid samples, error messages, labeled row count, total row count)."""
    samples: list[Sample] = []
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
            errors.append(f"{path.name}:{lineno}: invalid JSON ({e.msg})")
            continue

        if "label" in row:
            labeled += 1
        elif labeled_only:
            continue

        row_id = row.get("id", "?")
        modality = row.get("modality", "text")
        model = MODELS.get(modality)
        if model is None:
            errors.append(
                f"{path.name}:{lineno} [{row_id}] modality: unknown {modality!r}"
            )
            continue

        try:
            samples.append(model.model_validate(row))
        except ValidationError as e:
            for err in e.errors():
                field = ".".join(str(part) for part in err["loc"]) or "(row)"
                errors.append(f"{path.name}:{lineno} [{row_id}] {field}: {err['msg']}")

    return samples, errors, labeled, total


def check_file_level(samples: list[Sample], strict: bool) -> list[str]:
    errors: list[str] = []

    ids = Counter(s.id for s in samples)
    for sample_id, count in ids.items():
        if count > 1:
            errors.append(f"duplicate id {sample_id} ({count} rows)")

    # Language share only means something on the full text set.
    texts = [s for s in samples if isinstance(s, TextMeal)]
    if strict and texts:
        vi_share = sum(s.lang == "vi" for s in texts) / len(texts)
        if vi_share < MIN_VI_SHARE:
            errors.append(f"Vietnamese share {vi_share:.0%} < {MIN_VI_SHARE:.0%}")

    return errors


def print_table(title: str, counter: Counter, order: list[str] | None = None) -> None:
    total = sum(counter.values())
    print(f"\n{title}")
    for key in order or sorted(counter):
        n = counter.get(key, 0)
        print(f"  {key:<10} {n:>4}  {n / total:>5.0%}")


def tag_value(sample: Sample, prefix: str) -> str:
    return next(
        (t.removeprefix(prefix) for t in sample.tags if t.startswith(prefix)), "?"
    )


def print_distribution(samples: list[Sample]) -> None:
    if not samples:
        return
    print_table("modality", Counter(s.modality for s in samples))
    print_table("modality × split", Counter(f"{s.modality}/{s.split}" for s in samples))
    print_table(
        "kcal",
        Counter(kcal_bucket(s.label.calories) for s in samples),
        order=["0", *[name for _, name in KCAL_BUCKETS], "≥1000"],
    )

    texts = [s for s in samples if isinstance(s, TextMeal)]
    if texts:
        print("\n== text ==")
        print_table("group", Counter(s.group.value for s in texts))
        print_table("lang", Counter(s.lang for s in texts))
        print_table(
            "group × split", Counter(f"{s.group.value}/{s.split}" for s in texts)
        )

    images = [s for s in samples if isinstance(s, ImageMeal)]
    if images:
        print("\n== image ==")
        print_table("image source", Counter(s.images[0].source for s in images))
        print_table("kcal bin", Counter(tag_value(s, "kcal_") for s in images))
        print_table("ingredient group", Counter(tag_value(s, "ingr_") for s in images))
        print_table(
            "kcal bin × split",
            Counter(f"{tag_value(s, 'kcal_')}/{s.split}" for s in images),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        type=Path,
        nargs="*",
        default=DEFAULT_PATHS,
        help="JSONL files (default: data/text_v0.1.jsonl data/image_v0.1.jsonl, relative to the repo root)",
    )
    parser.add_argument(
        "--labeled-only",
        action="store_true",
        help="validate only rows that already have a label (use while labeling)",
    )
    args = parser.parse_args()

    samples: list[Sample] = []
    errors: list[str] = []
    for path in args.paths:
        file_samples, file_errors, labeled, total = load_and_validate(
            path, args.labeled_only
        )
        samples += file_samples
        errors += file_errors
        print(f"{path}: labeled {labeled}/{total}, valid {len(file_samples)}")
    errors += check_file_level(samples, strict=not args.labeled_only)

    print_distribution(samples)

    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for msg in errors:
            print(f"  {msg}", file=sys.stderr)
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
