"""Prepare an IOGP review corpus; never infer expert labels or activate a model."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re

TAGS = (
    "Bypassing Safety Controls", "Confined Space", "Driving", "Energy Isolation",
    "Hot Work", "Line of Fire", "Safe Mechanical Lifting", "Work Authorisation",
    "Working at Height",
)
ALIASES = {x.casefold(): x for x in TAGS}
ALIASES["work authorization"] = "Work Authorisation"
NO_RULE = "Other issue – no applicable rule"
SECTIONS = {
    "COUNTRY": "country", "FUNCTION": "function", "CAUSE": "cause",
    "ACTIVITY": "activity", "PRIMARY LIFE-SAVING RULE": "primary_rule",
    "SECONARY LIFE-SAVING RULE": "secondary_rule",
    "SECONDARY LIFE-SAVING RULE": "secondary_rule", "NARRATIVE": "narrative",
    "WHAT WENT WRONG": "what_went_wrong",
    "CORRECTIVE ACTIONS AND RECOMMENDATIONS": "corrective_actions",
    "CAUSAL FACTORS": "causal_factors",
}
REGION = re.compile(r"^(AFRICA|ASIA/AUSTRALASIA|EUROPE|MIDDLE EAST|NORTH AMERICA|"
                    r"RUSSIA & CENTRAL ASIA|SOUTH & CENTRAL AMERICA) (ONSHORE|OFFSHORE)$")
FIELDS = [
    "report_id", "description", "source_event_date", "source_country", "source_function",
    "source_activity", "source_primary_rule", "source_secondary_rule", "source_tags",
    "source_sif_status", "source_url", "source_pdf_sha256", "source_page_start", "source_page_end",
    "event_group", "label", "split", "hse_reviewed", "reviewer", "reviewed_at", "label_reason",
    "tag_reviewed", "lsr_tags", "actual_exposure", "exposure_evidence", "barrier_state",
    "barrier_evidence", "review_notes", "input_edit_reason", "is_synthetic", "report_type",
    "site", "event_timestamp", "training_use_status", "training_use_basis",
]


def digest(value):
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def normalize(text):
    return " ".join(text.casefold().split())


def rule_tag(value):
    if not value or value == NO_RULE:
        return None
    if value.casefold() not in ALIASES:
        raise ValueError(f"Unrecognised source rule: {value!r}")
    return ALIASES[value.casefold()]


def parse_pages(pages, source_id):
    """Parse page-spanning records and retain PDF page provenance (one based)."""
    records, current, section = [], None, None

    def finish():
        if current is None:
            return
        record = {k: "\n".join(v).strip() if isinstance(v, list) else v for k, v in current.items()}
        required = ["country", "function", "cause", "activity", "primary_rule", "narrative",
                    "what_went_wrong", "corrective_actions", "causal_factors"]
        missing = [k for k in required if not record.get(k)]
        if missing:
            raise ValueError(f"Incomplete event on page {record['page_start']}: {missing}")
        record["event_date"] = datetime.strptime(record["event_date"], "%d %b %Y").date().isoformat()
        record["source_tags"] = list(dict.fromkeys(filter(None, (
            rule_tag(record["primary_rule"]), rule_tag(record.get("secondary_rule", ""))))))
        record["record_id"] = f"{source_id}-{len(records)+1:04d}"
        record["narrative_sha256"] = digest(record["narrative"])
        record["event_group"] = "narrative-" + digest(normalize(record["narrative"]))[:20]
        records.append(record)

    for page_number, text in enumerate(pages, 1):
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if (not line or line.isdigit() or REGION.fullmatch(line)
                    or re.fullmatch(r"\d{4} safety data [–-] High potential event reports", line)):
                continue
            if line.startswith("This page is intentionally blank") or line.startswith("For the full analysis of"):
                finish()
                current, section = None, None
                break
            if line.startswith("DATE:"):
                finish()
                current = {"event_date": line.partition(":")[2].strip(),
                           "page_start": page_number, "page_end": page_number}
                section = None
                continue
            if current is None:
                continue
            current["page_end"] = page_number
            heading, sep, value = line.partition(":")
            if sep and heading in SECTIONS:
                section = SECTIONS[heading]
                current.setdefault(section, [])
                if value.strip():
                    current[section].append(value.strip())
            elif section:
                current[section].append(line)
    finish()
    if not records:
        raise ValueError("No IOGP events found; verify the PDF format or OCR first.")
    if len({r["record_id"] for r in records}) != len(records):
        raise ValueError("Duplicate record IDs.")
    return records


def review_rows(records, manifest):
    rows = []
    for r in records:
        row = dict.fromkeys(FIELDS, "")
        row.update(report_id=r["record_id"], description=r["narrative"],
                   source_event_date=r["event_date"], source_country=r["country"],
                   source_function=r["function"], source_activity=r["activity"],
                   source_primary_rule=r["primary_rule"], source_secondary_rule=r.get("secondary_rule", ""),
                   source_tags=json.dumps(r["source_tags"], ensure_ascii=False),
                   source_sif_status="PUBLISHER_HIGH_POTENTIAL", source_url=manifest["source_url"],
                   source_pdf_sha256=manifest["pdf_sha256"], source_page_start=r["page_start"],
                   source_page_end=r["page_end"], event_group=r["event_group"],
                   hse_reviewed="false", tag_reviewed="false", is_synthetic="false",
                   training_use_status="PENDING")
        rows.append(row)
    return rows


def eligibility_errors(row):
    errors = []
    for key, expected in [("hse_reviewed", "true"), ("is_synthetic", "false"),
                          ("training_use_status", "CLEARED")]:
        if row.get(key) != expected:
            errors.append(f"{key} must be {expected}")
    for key in ["reviewer", "reviewed_at", "label_reason", "training_use_basis", "event_group"]:
        if not row.get(key, "").strip():
            errors.append(f"{key} is required")
    if row.get("label") not in ("0", "1"):
        errors.append("label must be expert-confirmed 0 or 1")
    if row.get("split") not in ("train", "calibration", "validation", "test"):
        errors.append("split must be assigned")
    if row.get("report_type") not in ("Near Miss", "Incident", "Unsafe Act", "Unsafe Condition"):
        errors.append("report_type must be reviewed")
    if not row.get("description", "").strip():
        errors.append("description is empty")
    return errors


def audit(rows):
    reasons = Counter()
    for row in rows:
        reasons.update(eligibility_errors(row))
    groups = Counter(r["event_group"] for r in rows)
    return {
        "records": len(rows), "sif_training_eligible": sum(not eligibility_errors(r) for r in rows),
        "hse_reviewed": sum(r["hse_reviewed"] == "true" for r in rows),
        "source_primary_rules": dict(Counter(r["source_primary_rule"] for r in rows)),
        "source_tag_occurrences": dict(Counter(t for r in rows for t in json.loads(r["source_tags"]))),
        "confirmed_sif_labels": dict(Counter(r["label"] or "UNREVIEWED" for r in rows)),
        "duplicate_narrative_groups": {k: v for k, v in groups.items() if v > 1},
        "eligibility_blockers": dict(reasons),
        "limitations": [
            "Source high-potential status is not an independently adjudicated ASCENSION label.",
            "This source supplies no confirmed low-potential comparison population.",
            "Source tags are primary/secondary classifications, not exhaustive negative labels.",
            "A safety rule tag does not establish actual worker exposure or barrier failure.",
            "Narratives are retrospective; they require review for prediction-time availability.",
            "Exact-text groups do not replace cross-source near-duplicate incident review.",
        ],
    }


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def prepare(pdf, output, source_id, source_url):
    from pypdf import PdfReader
    raw = pdf.read_bytes()
    reader = PdfReader(io.BytesIO(raw))
    records = parse_pages([p.extract_text() or "" for p in reader.pages], source_id)
    manifest = {
        "schema_version": "ascension-pilot-1", "source_id": source_id,
        "source_url": source_url, "source_pdf": str(pdf.resolve()), "pdf_sha256": digest(raw),
        "pdf_pages": len(reader.pages), "records": len(records),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "REVIEW_ONLY", "training_use_status": "PENDING",
        "rights_note": "Supplied PDF permits attributed reproduction and reserves other uses; training reuse unconfirmed.",
        "extraction": "pypdf text extraction; section parser; no generated incident facts",
        "prediction_input": "narrative only; source labels and investigation sections stored separately",
    }
    rows = review_rows(records, manifest)
    summary = audit(rows)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "manifest.json", manifest)
    write_json(output / "audit.json", summary)
    write_json(output / "taxonomy.json", {"version": "iogp-lsr-nine-pilot-1", "tags": TAGS,
        "no_applicable_rule": NO_RULE, "note": "No-applicable-rule is not a tenth life-saving rule."})
    with (output / "source_records.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (output / "review.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    primary = "\n".join(f"| {k} | {v} |" for k, v in summary["source_primary_rules"].items())
    (output / "README.md").write_text(
        f"# IOGP pilot review corpus\n\nExtracted {len(rows)} source events from {len(reader.pages)} PDF pages.\n\n"
        "Status: REVIEW_ONLY. No labels have been HSE-confirmed and no model has been trained.\n\n"
        "Review `review.csv` using `docs/DATASET_PILOT.md`. `source_records.jsonl` preserves separate "
        "narrative and investigation sections with page references. Never feed the entire CSV or "
        "JSON record into the model. Only the reviewed description is exported as text input.\n\n"
        "All splits, model labels, and reviewed tag labels are intentionally unassigned. "
        "No-applicable-rule cases are still publisher high-potential events, not SIF negatives.\n\n"
        "## Source primary-rule counts (not reviewed training labels)\n\n"
        "| Primary rule | Events |\n|---|---:|\n" + primary + "\n\n"
        "Exact-duplicate detection is automatic; near-duplicate and cross-source checks remain necessary. "
        "See audit.json for eligibility blockers and tag counts including secondary tags.\n",
        encoding="utf-8")
    return summary


def load_review(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def export_sif(review, source_records, output):
    rows = load_review(review)
    if not rows:
        raise ValueError("Review dataset is empty.")
    originals = {r["record_id"]: r for r in (
        json.loads(line) for line in source_records.read_text(encoding="utf-8").splitlines() if line)}
    seen, groups, ids = set(), {}, set()
    for row in rows:
        problems = eligibility_errors(row)
        rid = row.get("report_id")
        if problems:
            raise ValueError(f"{rid}: " + "; ".join(problems))
        if rid not in originals or rid in ids:
            raise ValueError(f"Unknown or duplicate source record: {rid}")
        ids.add(rid)
        if row["description"] != originals[rid]["narrative"] and not row.get("input_edit_reason", "").strip():
            raise ValueError(f"{rid}: modified input needs input_edit_reason")
        text = normalize(row["description"])
        if text in seen:
            raise ValueError("Duplicate descriptions must be resolved before training.")
        seen.add(text)
        # Check both the reviewer's cross-source grouping and the immutable source grouping.
        for group in (row["event_group"], originals[rid]["event_group"]):
            if group in groups and groups[group] != row["split"]:
                raise ValueError("An event group crosses dataset splits.")
            groups[group] = row["split"]
    for split in ("train", "calibration", "validation", "test"):
        subset = [r for r in rows if r["split"] == split]
        if {r["label"] for r in subset} != {"0", "1"} or len(subset) < 10:
            raise ValueError(f"{split} needs both classes and at least 10 reviewed reports; this is only an experiment floor.")
    # Explicit allowlist: no source tags, outcome fields, or investigation conclusions enter training.
    fields = ["description", "label", "event_group", "split", "hse_reviewed", "is_synthetic",
              "report_type", "site", "event_timestamp"]
    with output.open("x", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return {"exported": len(rows), "output": str(output), "model_trained": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("pdf", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source-id", required=True)
    p.add_argument("--source-url", required=True)
    a = commands.add_parser("audit")
    a.add_argument("review", type=Path)
    e = commands.add_parser("export-sif")
    e.add_argument("review", type=Path)
    e.add_argument("--source-records", type=Path, required=True)
    e.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.pdf, args.output, args.source_id, args.source_url)
    elif args.command == "audit":
        result = audit(load_review(args.review))
    else:
        result = export_sif(args.review, args.source_records, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
