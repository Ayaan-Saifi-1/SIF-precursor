"""Create the final 50 real-record HSE review pack for the ASCENSION prototype.

The pack brings HSE-001 (100 records) and HSE-002 (100 records) to the planned
250-record prototype review target.  It contains no labels and has no training
eligibility: source permissions and HSE adjudication remain separate gates.
"""

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re


REVIEW_FIELDS = [
    "review_item_id", "description", "label", "lsr_tags", "actual_exposure",
    "exposure_evidence", "barrier_state", "barrier_evidence", "label_reason",
    "information_missing", "reviewer", "reviewed_at", "review_notes",
]

IADC_BUCKETS = {
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


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stable_key(namespace: str, record_id: str) -> str:
    return sha256(f"{namespace}|{record_id}".encode("utf-8")).hexdigest()


def description(record: dict) -> str:
    return (record.get("narrative") or record.get("source_text") or "").strip()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def take_iadc(records: list[dict], excluded_groups: set[str]) -> tuple[list[dict], dict[str, str]]:
    """Select 26 non-overlapping IADC reports by retrieval coverage, never labels."""
    selected, reasons = [], {}
    seen_groups = set(excluded_groups)
    seen_text = set()

    def take(candidates: list[dict], count: int, reason: str) -> None:
        added = 0
        for record in sorted(candidates, key=lambda r: stable_key("HSE-003", r["record_id"])):
            text = " ".join(description(record).lower().split())
            group = record.get("event_group") or record["record_id"]
            if not text or group in seen_groups or text in seen_text:
                continue
            selected.append(record)
            reasons[record["record_id"]] = reason
            seen_groups.add(group)
            seen_text.add(text)
            added += 1
            if added == count:
                return
        if added != count:
            raise ValueError(f"Insufficient IADC records for {reason}: {added}/{count}")

    for name, pattern in IADC_BUCKETS.items():
        matcher = re.compile(pattern, re.IGNORECASE)
        take([record for record in records if matcher.search(description(record))], 2,
             f"Retrieval coverage: {name}; not a target label")
    take(records, 8, "Unfiltered source comparison; not a negative label")
    if len(selected) != 26:
        raise ValueError(f"Expected 26 IADC records, got {len(selected)}")
    return selected, reasons


def build(bsee_dir: Path, iadc_dir: Path, existing_iadc_pack: Path, output: Path) -> None:
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    bsee = load_jsonl(bsee_dir / "source_records.jsonl")
    iadc = load_jsonl(iadc_dir / "source_records.jsonl")
    already_selected = load_jsonl(existing_iadc_pack / "source_records.jsonl")
    if len(bsee) != 24:
        raise ValueError(f"Expected the 24 screened BSEE alerts, found {len(bsee)}")
    if any(record.get("is_synthetic") for record in bsee + iadc):
        raise ValueError("Prototype review pack may not contain synthetic records")
    selected_iadc, iadc_reasons = take_iadc(
        iadc,
        {record.get("event_group") or record["record_id"] for record in already_selected},
    )
    selected = [
        (record, "BSEE_HISTORICAL_SAFETY_ALERTS", "Screened offshore incident collection; not a target label")
        for record in sorted(bsee, key=lambda r: stable_key("HSE-003", r["record_id"]))
    ] + [
        (record, "IADC_PUBLIC_ALERTS", iadc_reasons[record["record_id"]])
        for record in selected_iadc
    ]
    selected.sort(key=lambda item: stable_key("HSE-003-BLIND", item[0]["record_id"]))
    if len(selected) != 50 or len({record["record_id"] for record, _, _ in selected}) != 50:
        raise ValueError("Pack must contain 50 distinct source records")

    output.mkdir(parents=True)
    blanks, key, source_records = [], [], []
    for index, (record, collection, reason) in enumerate(selected, 1):
        text = description(record)
        if not text:
            raise ValueError(f"{record['record_id']}: missing narrative")
        item = f"HSE-003-{index:03d}"
        blanks.append({"review_item_id": item, "description": text})
        key.append({
            "review_item_id": item,
            "record_id": record["record_id"],
            "source_collection": collection,
            "source_url": record.get("source_url", ""),
            "selection_reason": reason,
        })
        source_records.append(record)

    write_csv(output / "reviewer_A.csv", blanks, REVIEW_FIELDS)
    write_csv(output / "reviewer_B.csv", blanks, REVIEW_FIELDS)
    write_csv(output / "review_key.csv", key, list(key[0]))
    adjudication_fields = [
        "review_item_id", "record_id", "description", "label", "lsr_tags", "actual_exposure",
        "exposure_evidence", "barrier_state", "barrier_evidence", "label_reason",
        "information_missing", "reviewer", "reviewed_at", "review_notes", "source_url",
    ]
    adjudication = [
        {**blank, "record_id": mapping["record_id"], "source_url": mapping["source_url"]}
        for blank, mapping in zip(blanks, key)
    ]
    write_csv(output / "adjudication.csv", adjudication, adjudication_fields)
    with (output / "source_records.jsonl").open("x", encoding="utf-8") as handle:
        for record in source_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "status": "REVIEW_ONLY",
        "batch_id": "HSE-003",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected_records": 50,
        "source_counts": {"BSEE_HISTORICAL_SAFETY_ALERTS": 24, "IADC_PUBLIC_ALERTS": 26},
        "synthetic_records": 0,
        "labels_assigned": 0,
        "training_eligible_records": 0,
        "prototype_review_total_after_this_batch": 250,
        "selection_policy": "All 24 screened BSEE narratives plus 26 IADC narratives excluding HSE-002 event groups. IADC selection uses nine retrieval buckets and unfiltered comparison; retrieval is not a label.",
        "review_blinding": "Reviewer forms contain narrative only and omit source IDs, publisher tags, source URLs and selection reason.",
        "limits": [
            "BSEE material is review-only until each item is screened for third-party or restricted content.",
            "IADC material is review-only pending documented training-reuse permission.",
            "Independent HSE review and adjudication are required before any training export.",
            "A reviewer decision does not by itself clear source material for model training.",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# HSE-003 prototype review pack\n\n"
        "This is the final 50-report pack for the 250-record ASCENSION prototype review target. "
        "It includes 24 BSEE offshore safety-alert narratives and 26 IADC drilling-alert narratives. "
        "All are real and unlabelled. Reviewer A and Reviewer B must work independently; use the review key only during adjudication. "
        "This pack is review-only and cannot be used for model training until its source permissions and HSE decisions are complete.\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bsee", type=Path, required=True)
    parser.add_argument("--iadc", type=Path, required=True)
    parser.add_argument("--existing-iadc-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    build(arguments.bsee, arguments.iadc, arguments.existing_iadc_pack, arguments.output)
