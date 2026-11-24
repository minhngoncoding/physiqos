"""Assign dev/test splits to a JSONL eval dataset.

Rules (docs/eval-spec.md §7.1): 70% dev / 30% test, stratified by modality,
group and language (Vietnamese vs. other), fixed seed. Deterministic: the same
file always gets the same split.

Usage:
    python scripts/split_dataset.py data/text_v0.1.jsonl            # dry run
    python scripts/split_dataset.py data/text_v0.1.jsonl --write    # update file

Run once, before any model output is inspected. Re-running after samples are
added reshuffles the strata, so freeze the split once it is committed.
"""

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

SEED = 42
TEST_RATIO = 0.3


def stratum(row: dict) -> tuple[str, str, str]:
    lang = "vi" if row["lang"] == "vi" else "non_vi"  # "mixed" goes with "en"
    return (row.get("modality", "text"), row["group"], lang)


def assign_splits(rows: list[dict], seed: int = SEED, test_ratio: float = TEST_RATIO) -> None:
    strata: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        strata[stratum(row)].append(row)

    for key in sorted(strata):
        members = sorted(strata[key], key=lambda r: r["id"])
        rng = random.Random(f"{seed}-{'-'.join(key)}")
        rng.shuffle(members)
        n_test = round(len(members) * test_ratio)
        for i, row in enumerate(members):
            row["split"] = "test" if i < n_test else "dev"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--write", action="store_true", help="overwrite the file in place")
    args = parser.parse_args()

    lines = args.path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    assign_splits(rows)

    counts = Counter((r["group"], r["split"]) for r in rows)
    print(f"{'group':<6}{'dev':>5}{'test':>6}")
    for group in sorted({r["group"] for r in rows}):
        print(f"{group:<6}{counts[(group, 'dev')]:>5}{counts[(group, 'test')]:>6}")
    total_test = sum(v for (_, s), v in counts.items() if s == "test")
    print(f"total {len(rows) - total_test:>5}{total_test:>6}")

    if args.write:
        with args.path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {args.path}")
    else:
        print("dry run, pass --write to update the file")


if __name__ == "__main__":
    main()
