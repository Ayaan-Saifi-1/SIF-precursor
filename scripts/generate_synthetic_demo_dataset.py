"""Generate a clearly marked, non-operational synthetic ASCENSION demo corpus.

Every record is constructed from templates. It exists only to exercise the demo
model and UI while real HSE review is pending. It must never be merged with real
review data or used for safety-performance claims.
"""

import argparse
import csv
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path


RULES = {
    "Bypassing Safety Controls": {
        "positive": "During a pressure test, the relief device was bypassed while personnel remained beside the separator.",
        "negative": "During a pressure test, the relief device was verified in service and personnel remained outside the exclusion area.",
    },
    "Confined Space": {
        "positive": "A technician entered a vessel before atmosphere testing was completed and without a documented entry permit.",
        "negative": "A technician entered the vessel after atmosphere testing, an entry permit and a standby attendant were confirmed.",
    },
    "Driving": {
        "positive": "A reversing service vehicle moved through a pedestrian work area without a spotter or separation barrier.",
        "negative": "A reversing service vehicle used a spotter and the pedestrian route was segregated before movement began.",
    },
    "Energy Isolation": {
        "positive": "Maintenance started on a pump after an isolation was removed, exposing the mechanic to unexpected energisation.",
        "negative": "Maintenance on the pump started only after lockout, tags and zero-energy verification were completed.",
    },
    "Hot Work": {
        "positive": "Grinding began near a hydrocarbon line without a gas test or fire watch in place.",
        "negative": "Grinding near the hydrocarbon line began after gas testing and a fire watch were confirmed.",
    },
    "Line of Fire": {
        "positive": "A worker placed a hand between moving equipment and a fixed support during alignment.",
        "negative": "The worker used a positioning tool and remained clear of the pinch point during alignment.",
    },
    "Safe Mechanical Lifting": {
        "positive": "A crew member entered beneath a suspended load while the load was being repositioned.",
        "negative": "The load was repositioned with an exclusion zone in place and all crew remained clear of the suspended load.",
    },
    "Work Authorisation": {
        "positive": "Work on a live process line continued after the permit conditions changed without reauthorisation.",
        "negative": "Work on the process line resumed only after the changed conditions were reviewed and the permit was reauthorised.",
    },
    "Working at Height": {
        "positive": "A worker worked at an open elevated edge without a connected fall-arrest system.",
        "negative": "A worker used a connected fall-arrest system and inspected the edge protection before work at height began.",
    },
}

SITES = ["Duliajan Field", "Moran Field", "Digboi Refinery", "Naharkatiya Field"]
DEPARTMENTS = ["Drilling", "Production", "Maintenance", "Projects"]
REPORT_TYPES = ["Near Miss", "Unsafe Condition", "Unsafe Act", "Incident"]
OPENERS = [
    "During the shift handover,", "During planned work,", "While the task was under way,",
    "Following a toolbox talk,", "During routine operations,", "At the start of the task,",
]
FOLLOWUPS = [
    "The task was stopped and escalated for review.", "The supervisor was notified and the area was made safe.",
    "No injury was reported; the exposure pathway was documented for follow-up.",
    "The event was recorded for HSE review and corrective action.",
]
WORK_STAGES = [
    "The task was in its preparation stage.", "The task was in its positioning stage.",
    "The task was in its execution stage.", "The task was in its close-out stage.",
    "The task was being restarted after a pause.", "The task was under routine supervision.",
]


def digest(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return sha256(payload).hexdigest()


def split_for(record_id: str) -> str:
    value = int(digest(record_id)[:8], 16) % 100
    return "train" if value < 60 else "calibration" if value < 75 else "validation" if value < 88 else "test"


def record(record_id: str, text: str, label: int, tags: list[str], family: str, index: int) -> dict:
    return {
        "record_id": record_id,
        "description": text,
        "label": str(label),
        "lsr_tags": json.dumps(tags),
        # Each generated row is a distinct fictitious event. Positive/negative
        # template alternatives must not be treated as one event that can cross
        # train/calibration/validation/test splits.
        "event_group": f"SYNTHETIC-DEMO-EVENT-{record_id}",
        "split": split_for(record_id),
        "hse_reviewed": "false",
        "is_synthetic": "true",
        "report_type": REPORT_TYPES[index % len(REPORT_TYPES)],
        "site": SITES[index % len(SITES)],
        "department": DEPARTMENTS[index % len(DEPARTMENTS)],
        "event_timestamp": (date(2025, 1, 1) + timedelta(days=index)).isoformat() + "T08:00:00+05:30",
        "source": "ASCENSION_TEMPLATE_GENERATOR",
        "synthesis_notice": "SYNTHETIC_DEVELOPMENT_ONLY; not a real incident, HSE label or validation record.",
    }


def generate() -> list[dict]:
    rows, counter = [], 1
    for rule_index, (rule, templates) in enumerate(RULES.items(), 1):
        for label_name, label in (("positive", 1), ("negative", 0)):
            for variant in range(32):
                text = " ".join([
                    OPENERS[(variant + rule_index) % len(OPENERS)],
                    f"At {SITES[(variant + rule_index) % len(SITES)]},",
                    templates[label_name],
                    WORK_STAGES[(variant // 12) % len(WORK_STAGES)],
                    FOLLOWUPS[(variant + label) % len(FOLLOWUPS)],
                ])
                rows.append(record(f"SYN-DEMO-{counter:04d}", text, label, [rule], rule_index, variant + 1))
                counter += 1
    pairs = [
        ("Energy Isolation", "Line of Fire"), ("Safe Mechanical Lifting", "Line of Fire"),
        ("Hot Work", "Work Authorisation"), ("Confined Space", "Work Authorisation"),
        ("Driving", "Line of Fire"),
    ]
    for pair_index, (first, second) in enumerate(pairs, 1):
        for variant in range(18):
            positive = " ".join([
                OPENERS[variant % len(OPENERS)], RULES[first]["positive"], RULES[second]["positive"],
                f"The task took place at {SITES[variant % len(SITES)]}.",
                WORK_STAGES[(variant // 12) % len(WORK_STAGES)],
                FOLLOWUPS[variant % len(FOLLOWUPS)],
            ])
            negative = " ".join([
                OPENERS[(variant + 1) % len(OPENERS)], RULES[first]["negative"], RULES[second]["negative"],
                f"The task took place at {SITES[(variant + 1) % len(SITES)]}.",
                WORK_STAGES[(variant // 12) % len(WORK_STAGES)],
                FOLLOWUPS[(variant + 1) % len(FOLLOWUPS)],
            ])
            rows.append(record(f"SYN-DEMO-{counter:04d}", positive, 1, [first, second], 20 + pair_index, variant + 1)); counter += 1
            rows.append(record(f"SYN-DEMO-{counter:04d}", negative, 0, [first, second], 20 + pair_index, variant + 1)); counter += 1
    for variant in range(72):
        text = " ".join([
            OPENERS[variant % len(OPENERS)],
            "A housekeeping observation was recorded with no identified high-energy hazard, direct exposure or weakened critical control.",
            f"The observation was logged at {SITES[variant % len(SITES)]} by {DEPARTMENTS[(variant // len(SITES)) % len(DEPARTMENTS)]}.",
            WORK_STAGES[(variant // 12) % len(WORK_STAGES)],
            FOLLOWUPS[variant % len(FOLLOWUPS)],
        ])
        rows.append(record(f"SYN-DEMO-{counter:04d}", text, 0, [], 99, variant + 1)); counter += 1
    return rows


def validate(rows: list[dict]) -> None:
    if not rows or any(row["is_synthetic"] != "true" for row in rows):
        raise ValueError("Synthetic marker missing")
    if len({row["record_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate synthetic record IDs")
    if len({row["description"] for row in rows}) != len(rows):
        raise ValueError("Duplicate synthetic narratives")
    for split in ("train", "calibration", "validation", "test"):
        labels = {row["label"] for row in rows if row["split"] == split}
        if labels != {"0", "1"}:
            raise ValueError(f"Synthetic {split} split must contain both classes")


def main(output: Path) -> None:
    rows = generate()
    validate(rows)
    fields = list(rows[0])
    records_path = output / "synthetic_demo_records.csv"
    if output.exists():
        # A prior interrupted generation may have written the data before its
        # manifest. Resume only when the directory contains that exact artifact.
        if (output / "manifest.json").exists() or not records_path.exists() or len(list(output.iterdir())) != 1:
            raise ValueError(f"Output already exists: {output}")
        with records_path.open(encoding="utf-8-sig", newline="") as handle:
            existing = list(csv.DictReader(handle))
        if existing != rows:
            raise ValueError("Existing incomplete synthetic dataset differs from this generator")
    else:
        output.mkdir(parents=True)
        with records_path.open("x", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
    manifest = {
        "status": "SYNTHETIC_DEVELOPMENT_ONLY",
        "records": len(rows),
        "rules": list(RULES),
        "labels": {"1": "template-defined SIF-potential development label", "0": "template-defined non-SIF development label"},
        "split_counts": {split: sum(row["split"] == split for row in rows) for split in ("train", "calibration", "validation", "test")},
        "sha256": digest((output / "synthetic_demo_records.csv").read_bytes()),
        "prohibitions": [
            "Do not merge with real reports or reviewer labels.",
            "Do not use for safety-model validation, calibration, performance claims or production decisions.",
            "Do not represent any row as an OIL, IADC, BSEE, IOGP or other real incident.",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
