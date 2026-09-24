"""Build a blinded, unlabelled HSE review batch from the IADC source pack."""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re


BUCKETS = {
    "lifting": r"\b(crane|lift(?:ing)?|hoist|sling|rigg(?:ing)?|load)\b",
    "pressure": r"\b(pressure|psi|hose|hydraulic|pneumatic|pressuri[sz])\b",
    "isolation": r"\b(lockout|tagout|isolat(?:e|ed|ion)|de-?energ|stored energy)\b",
    "line_of_fire": r"\b(line of fire|struck|caught|pinch|recoil|eject(?:ed|ion)?)\b",
    "height": r"\b(fall(?:ing)?|ladder|derrick|elevat(?:ed|ion)|work(?:ing)? at height)\b",
    "confined_space": r"\b(confined space|tank|vessel|enclosed space)\b",
    "fire_explosion": r"\b(fire|explosion|ignition|gas release|hydrocarbon)\b",
    "vehicles": r"\b(vehicle|forklift|driving|truck|transport)\b",
    "well_control": r"\b(blowout|\bbop\b|well control|kick)\b",
}
PER_BUCKET = 10

REVIEW_FIELDS = [
    "review_item_id", "description", "label", "lsr_tags", "actual_exposure",
    "exposure_evidence", "barrier_state", "barrier_evidence", "label_reason",
    "information_missing", "reviewer", "reviewed_at", "review_notes",
]


def stable_order(record_id):
    return sha256(("HSE-002|" + record_id).encode("utf-8")).hexdigest()


def write_csv(path, rows, fields):
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(source, output):
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    records = [json.loads(line) for line in (source / "source_records.jsonl").read_text(encoding="utf-8").splitlines()]
    if not records:
        raise ValueError("No IADC source records found")
    if any(r["sif_status"] != "NOT_ASSIGNED" or r["lsr_tags"] or r["is_synthetic"] for r in records):
        raise ValueError("IADC source pack must remain unlabelled and non-synthetic")
    selected, selected_ids, event_groups, selection = [], set(), set(), {}

    def take(candidates, count, reason):
        taken = 0
        for record in sorted(candidates, key=lambda r: stable_order(r["record_id"])):
            if record["record_id"] in selected_ids or record["event_group"] in event_groups:
                continue
            selected.append(record)
            selected_ids.add(record["record_id"])
            event_groups.add(record["event_group"])
            selection[record["record_id"]] = reason
            taken += 1
            if taken == count:
                break
        if taken != count:
            raise ValueError(f"Insufficient distinct records for {reason}: {taken}/{count}")

    for name, pattern in BUCKETS.items():
        matcher = re.compile(pattern, re.IGNORECASE)
        take([r for r in records if matcher.search(r["narrative"])], PER_BUCKET, f"Retrieval coverage: {name}; not a target label")
    take(records, 100 - len(selected), "Unfiltered source comparison; not a negative label")
    selected.sort(key=lambda r: stable_order("BLIND-ORDER|" + r["record_id"]))
    if len(selected) != 100 or len({r["event_group"] for r in selected}) != 100:
        raise ValueError("Selection must contain 100 distinct event groups")

    output.mkdir(parents=True)
    blanks, key = [], []
    for index, record in enumerate(selected, 1):
        item = f"HSE-002-{index:03d}"
        blanks.append({"review_item_id": item, "description": record["narrative"]})
        key.append({
            "review_item_id": item, "record_id": record["record_id"],
            "source_url": record["source_url"], "source_collection": record["source_collection"],
            "selection_reason": selection[record["record_id"]],
        })
    write_csv(output / "reviewer_A.csv", blanks, REVIEW_FIELDS)
    write_csv(output / "reviewer_B.csv", blanks, REVIEW_FIELDS)
    write_csv(output / "review_key.csv", key, list(key[0]))
    adjudication_fields = [
        "review_item_id", "record_id", "description", "label", "lsr_tags", "actual_exposure",
        "exposure_evidence", "barrier_state", "barrier_evidence", "label_reason",
        "information_missing", "reviewer", "reviewed_at", "review_notes", "source_url",
    ]
    adjudication = []
    for blank, mapping, record in zip(blanks, key, selected):
        adjudication.append({**blank, **mapping, "record_id": record["record_id"]})
    write_csv(output / "adjudication.csv", adjudication, adjudication_fields)
    with (output / "source_records.jsonl").open("x", encoding="utf-8") as handle:
        for record in selected:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest = {
        "status": "REVIEW_ONLY",
        "batch_id": "HSE-002",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_collection": "IADC_PUBLIC_ALERTS",
        "source_pool_records": len(records),
        "selected_records": len(selected),
        "synthetic_records": 0,
        "labels_assigned": 0,
        "training_eligible_records": 0,
        "selection_policy": "Nine text retrieval buckets plus one unfiltered comparison group; retrieval never assigns a target label.",
        "review_blinding": "Reviewer A/B files contain narrative only and omit source IDs, source tags, retrieval bucket and source URLs.",
        "limits": [
            "IADC material remains review-only pending training-reuse permission.",
            "Source outcome language and publisher metadata are not target labels.",
            "Two independent HSE reviews and adjudication are required before any training export.",
        ],
    }
    write_json(output / "manifest.json", manifest)
    (output / "README.md").write_text(
        "# HSE-002 IADC blinded review pack\n\n"
        "This pack contains 100 real IADC drilling-alert narratives selected for review coverage. "
        "It contains no SIF labels or ASCENSION life-saving-rule labels.\n\n"
        "Reviewer A and Reviewer B must label independently. Use the review key only after first-pass review. "
        "The material is review-only until IADC training reuse permission is documented.\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
