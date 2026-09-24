"""Reconcile returned independent HSE review files without creating labels.

The tool validates that reviewers returned the assigned narratives unchanged,
normalises the allowed review values, and produces an adjudication workspace. It
never turns reviewer agreement into an approved ASCENSION label.
"""

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path


REVIEW_FIELDS = [
    "review_item_id", "description", "label", "lsr_tags", "actual_exposure",
    "exposure_evidence", "barrier_state", "barrier_evidence", "label_reason",
    "information_missing", "reviewer", "reviewed_at", "review_notes",
]
FINAL_FIELDS = [
    "label", "lsr_tags", "actual_exposure", "exposure_evidence", "barrier_state",
    "barrier_evidence", "label_reason", "information_missing", "reviewer",
    "reviewed_at", "review_notes",
]
CANONICAL_TAGS = {
    "bypassing safety controls": "Bypassing Safety Controls",
    "confined space": "Confined Space",
    "driving": "Driving",
    "energy isolation": "Energy Isolation",
    "hot work": "Hot Work",
    "line of fire": "Line of Fire",
    "safe mechanical lifting": "Safe Mechanical Lifting",
    "mechanical lifting": "Safe Mechanical Lifting",
    "work authorisation": "Work Authorisation",
    "work authorization": "Work Authorisation",
    "working at height": "Working at Height",
    "work at height": "Working at Height",
}
VALID_BARRIER_STATES = {
    "EFFECTIVE", "DEGRADED", "FAILED", "BYPASSED", "ABSENT", "UNVERIFIED", "UNKNOWN",
}
VALID_LABELS = {"0", "1", "UNCERTAIN", "REVIEW"}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def value(row: dict, key: str) -> str:
    return (row.get(key) or "").strip()


def normalized_label(row: dict) -> str:
    raw = value(row, "label").upper()
    if not raw:
        return "UNREVIEWED"
    if raw not in VALID_LABELS:
        raise ValueError(f"{row['review_item_id']}: invalid label {raw!r}")
    return raw


def normalized_tags(row: dict) -> tuple[tuple[str, ...] | None, list[str]]:
    raw = value(row, "lsr_tags")
    if not raw:
        return None, []
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not all(isinstance(tag, str) for tag in parsed):
            raise ValueError
        values = parsed
    except (json.JSONDecodeError, ValueError):
        values = raw.split(";")
    result, invalid = [], []
    for tag in values:
        normalized = " ".join(tag.strip().casefold().split())
        if not normalized:
            continue
        canonical = CANONICAL_TAGS.get(normalized)
        if canonical is None:
            invalid.append(tag.strip())
        elif canonical not in result:
            result.append(canonical)
    return tuple(sorted(result)), invalid


def validate_returned(rows: list[dict], expected: dict[str, dict], reviewer_name: str) -> dict[str, dict]:
    if not rows:
        raise ValueError(f"{reviewer_name}: file is empty")
    if set(rows[0]) != set(REVIEW_FIELDS):
        raise ValueError(f"{reviewer_name}: columns changed; return the supplied CSV structure")
    result = {}
    for row in rows:
        item = value(row, "review_item_id")
        if item not in expected or item in result:
            raise ValueError(f"{reviewer_name}: unknown or duplicate review_item_id {item!r}")
        if row.get("description", "") != expected[item]["description"]:
            raise ValueError(f"{reviewer_name}: {item} description changed")
        result[item] = row
    missing = sorted(set(expected) - set(result))
    if missing:
        raise ValueError(f"{reviewer_name}: missing assigned review items: {missing[:5]}")
    return result


def scalar_agreement(left: dict, right: dict, key: str) -> str:
    a, b = value(left, key), value(right, key)
    if not a and not b:
        return "BOTH_BLANK"
    return "AGREE" if a.casefold() == b.casefold() else "DIFFER"


def reconcile(pack: Path, reviewer_a: Path, reviewer_b: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    template = read_csv(pack / "reviewer_A.csv")
    expected = {row["review_item_id"]: row for row in template}
    if not expected or len(expected) != len(template):
        raise ValueError("Pack template has missing or duplicate review_item_id values")
    key_rows = read_csv(pack / "review_key.csv")
    source_rows = {row["record_id"]: row for row in read_csv(pack / "adjudication.csv")}
    key_by_item = {row["review_item_id"]: row for row in key_rows}
    if set(key_by_item) != set(expected):
        raise ValueError("Pack review key does not match reviewer template")
    a = validate_returned(read_csv(reviewer_a), expected, "Reviewer A")
    b = validate_returned(read_csv(reviewer_b), expected, "Reviewer B")

    output.mkdir(parents=True)
    rows, invalid_tags, label_counts = [], [], Counter()
    for item in sorted(expected):
        left, right = a[item], b[item]
        left_label, right_label = normalized_label(left), normalized_label(right)
        left_tags, left_invalid = normalized_tags(left)
        right_tags, right_invalid = normalized_tags(right)
        if left_invalid or right_invalid:
            invalid_tags.append({
                "review_item_id": item,
                "reviewer_a_invalid_tags": left_invalid,
                "reviewer_b_invalid_tags": right_invalid,
            })
        label_counts[f"A:{left_label}"] += 1
        label_counts[f"B:{right_label}"] += 1
        source = source_rows[key_by_item[item]["record_id"]]
        label_agreement = (
            "AGREE" if left_label == right_label and left_label in {"0", "1"}
            else "BOTH_UNREVIEWED" if left_label == right_label == "UNREVIEWED"
            else "REQUIRES_ADJUDICATION"
        )
        tags_agreement = (
            "AGREE" if left_tags is not None and right_tags is not None and left_tags == right_tags
            else "BOTH_UNREVIEWED" if left_tags is None and right_tags is None
            else "REQUIRES_ADJUDICATION"
        )
        # Final fields intentionally remain blank. Agreement is evidence for the
        # adjudicator, never an automatic final label or tag decision.
        row = {
            "review_item_id": item,
            "record_id": key_by_item[item]["record_id"],
            "description": expected[item]["description"],
            "source_url": source.get("source_url", ""),
            "reviewer_a_label": left_label,
            "reviewer_b_label": right_label,
            "sif_agreement": label_agreement,
            "reviewer_a_lsr_tags": "; ".join(left_tags or ()),
            "reviewer_b_lsr_tags": "; ".join(right_tags or ()),
            "tag_agreement": tags_agreement,
            "reviewer_a_actual_exposure": value(left, "actual_exposure"),
            "reviewer_b_actual_exposure": value(right, "actual_exposure"),
            "exposure_agreement": scalar_agreement(left, right, "actual_exposure"),
            "reviewer_a_barrier_state": value(left, "barrier_state").upper(),
            "reviewer_b_barrier_state": value(right, "barrier_state").upper(),
            "barrier_agreement": scalar_agreement(left, right, "barrier_state"),
            **{f"final_{field}": "" for field in FINAL_FIELDS},
            "adjudication_status": "READY" if label_agreement == "AGREE" and tags_agreement == "AGREE" else "REQUIRED",
        }
        rows.append(row)

    invalid_barriers = [
        {"review_item_id": row["review_item_id"], "reviewer": reviewer, "value": row[column]}
        for row in rows
        for reviewer, column in (("A", "reviewer_a_barrier_state"), ("B", "reviewer_b_barrier_state"))
        if row[column] and row[column] not in VALID_BARRIER_STATES
    ]
    fields = list(rows[0])
    write_csv(output / "adjudication_workspace.csv", rows, fields)
    report = {
        "status": "ADJUDICATION_REQUIRED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pack": str(pack),
        "reviewer_a_file": str(reviewer_a),
        "reviewer_b_file": str(reviewer_b),
        "records": len(rows),
        "sif": dict(Counter(row["sif_agreement"] for row in rows)),
        "life_saving_rule_tags": dict(Counter(row["tag_agreement"] for row in rows)),
        "exposure": dict(Counter(row["exposure_agreement"] for row in rows)),
        "barrier_state": dict(Counter(row["barrier_agreement"] for row in rows)),
        "reviewer_label_counts": dict(label_counts),
        "invalid_tags": invalid_tags,
        "invalid_barrier_states": invalid_barriers,
        "final_labels_assigned": 0,
        "training_eligible_records": 0,
        "limitations": [
            "Agreement is not an adjudicated HSE decision.",
            "No final label, tag or training export is produced by this tool.",
            "Source reuse permissions remain independent from review completion.",
        ],
    }
    (output / "reconciliation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True, help="Original HSE review pack directory")
    parser.add_argument("--reviewer-a", type=Path, required=True, help="Completed Reviewer A CSV")
    parser.add_argument("--reviewer-b", type=Path, required=True, help="Completed Reviewer B CSV")
    parser.add_argument("--output", type=Path, required=True, help="New adjudication output directory")
    args = parser.parse_args()
    reconcile(args.pack, args.reviewer_a, args.reviewer_b, args.output)
