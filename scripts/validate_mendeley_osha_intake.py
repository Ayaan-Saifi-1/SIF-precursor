"""Create a transparent quality report for the auxiliary OSHA narrative intake."""

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def inspect(path: Path, is_validation: bool) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    bad_rows = []
    narratives = []
    for number, row in enumerate(rows, start=2):
        narrative = row.get("Final Narrative", "").strip()
        narratives.append(narrative)
        reasons = []
        if not narrative:
            reasons.append("blank_narrative")
        if row.get(None):
            reasons.append("extra_csv_columns")
        if is_validation and row.get("Is_Correct") not in {"0", "1"}:
            reasons.append("invalid_is_correct")
        if reasons:
            bad_rows.append({
                "line": number,
                "source_id": row.get("ID", ""),
                "reasons": reasons,
                "narrative_sha256": sha256(narrative.encode("utf-8")).hexdigest(),
            })
    bad_lines = {entry["line"] for entry in bad_rows}
    return {
        "filename": path.name,
        "sha256": file_sha256(path),
        "records_read": len(rows),
        "blank_narratives": sum(not value for value in narratives),
        "unique_narratives": len(set(narratives)),
        "quality_eligible_records": len(rows) - len(bad_lines),
        "excluded_records": bad_rows,
    }


def main(root: Path) -> None:
    source = root / "source_files"
    master = inspect(source / "Final_Master_Ensemble_v18_Success_Deidentified.csv", False)
    validation = inspect(source / "Gemini_Final_Validation_400_Deidentified.csv", True)
    report = {
        "status": "AUXILIARY_RESEARCH_ONLY",
        "quality_policy": (
            "Malformed source rows are excluded only from experiments; originals remain "
            "unchanged under source_files for reproducibility."
        ),
        "master": master,
        "validation": validation,
        "sif_or_life_saving_rule_labels_created": 0,
        "oil_and_gas_validation_claims": 0,
    }
    (root / "quality_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    main(parser.parse_args().root)
