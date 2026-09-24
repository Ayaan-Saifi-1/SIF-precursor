"""Build a candidate dataset only from final HSE decisions and cleared sources.

This command intentionally cannot infer labels, clear source rights, or assign
train/test splits.  It turns completed adjudication workspaces into one
traceable candidate CSV for the later split-and-train step.
"""

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


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
OUTPUT_FIELDS = [
    "report_id", "description", "label", "lsr_tags", "event_group", "split",
    "hse_reviewed", "reviewer", "reviewed_at", "label_reason", "actual_exposure",
    "exposure_evidence", "barrier_state", "barrier_evidence", "review_notes",
    "is_synthetic", "report_type", "site", "event_timestamp", "source_collection",
    "source_url", "training_use_status", "training_use_basis",
]
CLEARANCE_FIELDS = ["record_id", "training_use_status", "training_use_basis"]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def description(record: dict) -> str:
    return (record.get("narrative") or record.get("source_text") or "").strip()


def normalise_tags(value: str) -> str:
    if not value.strip():
        return ""
    tags, unknown = [], []
    for raw_tag in value.split(";"):
        key = " ".join(raw_tag.casefold().split())
        if not key:
            continue
        tag = CANONICAL_TAGS.get(key)
        if tag is None:
            unknown.append(raw_tag.strip())
        elif tag not in tags:
            tags.append(tag)
    if unknown:
        raise ValueError(f"Unknown final life-saving-rule tag(s): {unknown}")
    return "; ".join(tags)


def load_clearances(path: Path) -> dict[str, dict]:
    rows = read_csv(path)
    if not rows or set(rows[0]) != set(CLEARANCE_FIELDS):
        raise ValueError("Clearance file must have exactly: " + ", ".join(CLEARANCE_FIELDS))
    clearances = {}
    for row in rows:
        record_id = (row.get("record_id") or "").strip()
        if not record_id or record_id in clearances:
            raise ValueError("Clearance file has a missing or duplicate record_id")
        if (row.get("training_use_status") or "").strip().upper() != "CLEARED":
            raise ValueError(f"{record_id}: training_use_status must be CLEARED")
        if not (row.get("training_use_basis") or "").strip():
            raise ValueError(f"{record_id}: training_use_basis is required")
        clearances[record_id] = row
    return clearances


def source_records(pack: Path) -> dict[str, dict]:
    source_path = pack / "source_records.jsonl"
    records = {}
    for line in source_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        record_id = record.get("record_id")
        if not record_id or record_id in records:
            raise ValueError(f"{source_path}: missing or duplicate record_id")
        if record.get("is_synthetic") is True:
            raise ValueError(f"{record_id}: synthetic source records are never eligible")
        records[record_id] = record
    return records


def export(workspaces: list[Path], packs: list[Path], clearances: dict[str, dict], output: Path) -> dict:
    if len(workspaces) != len(packs):
        raise ValueError("Pass the same number of --workspace and --source-pack arguments")
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    rows, seen_ids, seen_descriptions = [], set(), set()
    for workspace_path, pack in zip(workspaces, packs):
        sources = source_records(pack)
        workspace = read_csv(workspace_path)
        if not workspace:
            raise ValueError(f"{workspace_path}: no adjudication records")
        for final in workspace:
            record_id = (final.get("record_id") or "").strip()
            label = (final.get("final_label") or "").strip()
            reviewer = (final.get("final_reviewer") or "").strip()
            reviewed_at = (final.get("final_reviewed_at") or "").strip()
            reason = (final.get("final_label_reason") or "").strip()
            if label not in {"0", "1"}:
                raise ValueError(f"{record_id}: final_label must be adjudicated 0 or 1; uncertain records stay unlabelled")
            if not reviewer or not reviewed_at or not reason:
                raise ValueError(f"{record_id}: final reviewer, date and label reason are required")
            if record_id not in sources or record_id in seen_ids:
                raise ValueError(f"{record_id}: source record is missing or duplicated across packs")
            if record_id not in clearances:
                raise ValueError(f"{record_id}: no documented source training clearance")
            source = sources[record_id]
            text = (final.get("description") or "").strip()
            if text != description(source):
                raise ValueError(f"{record_id}: adjudication description differs from immutable source narrative")
            normalized = " ".join(text.casefold().split())
            if normalized in seen_descriptions:
                raise ValueError(f"{record_id}: duplicate narrative requires event-level resolution")
            seen_ids.add(record_id)
            seen_descriptions.add(normalized)
            clearance = clearances[record_id]
            collection = source.get("source_collection", "")
            group = source.get("event_group") or f"{collection}:{record_id}"
            rows.append({
                "report_id": record_id,
                "description": text,
                "label": label,
                "lsr_tags": normalise_tags(final.get("final_lsr_tags") or ""),
                "event_group": group,
                "split": "PENDING",
                "hse_reviewed": "true",
                "reviewer": reviewer,
                "reviewed_at": reviewed_at,
                "label_reason": reason,
                "actual_exposure": (final.get("final_actual_exposure") or "").strip(),
                "exposure_evidence": (final.get("final_exposure_evidence") or "").strip(),
                "barrier_state": (final.get("final_barrier_state") or "").strip(),
                "barrier_evidence": (final.get("final_barrier_evidence") or "").strip(),
                "review_notes": (final.get("final_review_notes") or "").strip(),
                "is_synthetic": "false",
                "report_type": "Unspecified",
                "site": "",
                "event_timestamp": "",
                "source_collection": collection,
                "source_url": source.get("source_url", ""),
                "training_use_status": "CLEARED",
                "training_use_basis": clearance["training_use_basis"].strip(),
            })
    if not rows:
        raise ValueError("No records exported")
    rows.sort(key=lambda row: row["report_id"])
    write_csv(output, rows, OUTPUT_FIELDS)
    raw = output.read_bytes()
    summary = {
        "status": "CANDIDATE_DATASET_PENDING_SPLIT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "records": len(rows),
        "label_counts": dict(Counter(row["label"] for row in rows)),
        "tag_counts": dict(Counter(tag for row in rows for tag in row["lsr_tags"].split("; ") if tag)),
        "source_counts": dict(Counter(row["source_collection"] for row in rows)),
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "limitations": [
            "This is not a trained model and has no assigned train/calibration/validation/test split.",
            "Report type is Unspecified because this review form does not ask reviewers to classify report type.",
            "Source clearance and final HSE adjudication are checked record by record.",
            "Uncertain cases are deliberately excluded from this supervised export.",
        ],
    }
    summary_path = output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, action="append", required=True,
                        help="Completed adjudication_workspace.csv; repeat once per source pack")
    parser.add_argument("--source-pack", type=Path, action="append", required=True,
                        help="Original HSE pack directory; keep the same order as --workspace")
    parser.add_argument("--source-clearance", type=Path, required=True,
                        help="CSV recording approved training rights for every record")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export(args.workspace, args.source_pack, load_clearances(args.source_clearance), args.output)
    print(json.dumps(result, indent=2))
