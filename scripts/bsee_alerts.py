"""Collect a small, source-backed BSEE Safety Alert review pool.

The alerts remain review material.  This importer does not infer ASCENSION SIF
status or life-saving-rule labels, and it preserves original PDFs and checksums.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import Request, urlopen


ARCHIVE_URL = "https://www.bsee.gov/newsroom/library/regulatory-archives/historical-bsee-safety-alerts"
BSEE_NOTICE = "https://www.bsee.gov/bsee/privacy-policy"

# Single-event reports selected for offshore coverage.  Deliberate exclusions:
# catalogues, multi-incident summaries and duplicate/revised alerts.
ALERTS = [
    (286, "Fire Inside AC Evaporator Enclosure", "https://bsee.gov/sites/bsee.gov/files/safety-alerts/incident-and-investigations/sa-286-pdf.pdf"),
    (283, "Crane Shock-Loading from Casing Jack Hydraulic Hose Fitting Failure", "https://bsee.gov/sites/bsee.gov/files/safety-alerts/incident-and-investigations/sa-283-pdf.pdf"),
    (272, "Corroded Ring Gasket Causes Loss of Well Control", "https://bsee.gov/sites/bsee.gov/files/safety-alerts/incident-and-investigations/sa-272-pdf.pdf"),
    (262, "Sudden Crane Boom Crash Injures One", "https://bsee.gov/sites/bsee.gov/files/safety-alerts/incident-and-investigations/sa-262-pdf.pdf"),
    (239, "Casing Bleed-down into Plastic Drum Results in Fire on Platform", "https://bsee.gov/sites/bsee.gov/files/safety-alerts/incident-and-investigations/sa-239-pdf.pdf"),
    (227, "Explosion and Fire from Improper Welding and Burning Practice", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-227.pdf"),
    (226, "Pressure Rise after Cementing Leads to Burst Casing and Loss of Control", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-226.pdf"),
    (221, "Hanger Failure and Ejection Lead to Well Control Incident", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/blowout-prevention/safety-alert-no-221.pdf"),
    (219, "Loss of Well Control while Drilling Surface Hole", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-219.pdf"),
    (209, "Crane Accident on the Norwegian OCS", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-209.pdf"),
    (206, "Fall Through V-Door Opening Results in Fatality", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-206.pdf"),
    (199, "Blowout and Fire", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/blowout-prevention/safety-alert-no-199.pdf"),
    (183, "Electrical Shock Hazard", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-183.pdf"),
    (167, "Retrieval of Back-Pressure Valve Results in Loss of Well Control", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-167.pdf"),
    (166, "Lifting of Personnel by Crane Proves Fatal", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-166.pdf"),
    (159, "Welder Burned in Pipeline Accident", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-159.pdf"),
    (154, "Flash Fire During Portable Well Testing Operations", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-154.pdf"),
    (150, "Fire During Cutting Operation to Install Casing Head", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-150.pdf"),
    (147, "Fire from Generator Engine Exhaust Leak", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-147.pdf"),
    (138, "Fire and Injury During Welding Operations in Derrick", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-138.pdf"),
    (124, "Pedestal Crane Boom Wire Rope Failure", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-124.pdf"),
    (104, "Crane Accident", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/safety/safety-alert-no-104.pdf"),
    (83, "Fire - Oil Sprays from Valve", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/incident-and-investigations/safety-alert-no-83.pdf"),
    (39, "Fire - Hydraulic Hose Ruptures", "https://www.bsee.gov/sites/bsee.gov/files/safety-alerts/incident-and-investigations/safety-alert-no-39.pdf"),
]


def fetch(url):
    request = Request(url, headers={"User-Agent": "ASCENSION-review-intake/1.0"})
    with urlopen(request, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f"BSEE returned HTTP {response.status} for {url}")
        content_type = response.headers.get("Content-Type", "")
        payload = response.read()
    if not payload.startswith(b"%PDF"):
        raise RuntimeError(f"Expected PDF from BSEE, received {content_type!r} for {url}")
    return payload


def collect(output):
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    import pdfplumber

    output.mkdir(parents=True)
    raw = output / "raw"
    raw.mkdir()
    records = []
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for number, title, url in ALERTS:
        payload = fetch(url)
        filename = f"BSEE-SA-{number:03d}.pdf"
        (raw / filename).write_bytes(payload)
        with pdfplumber.open(raw / filename) as document:
            text = "\n\n".join((page.extract_text() or "").strip() for page in document.pages).strip()
            page_count = len(document.pages)
        if len(text) < 100:
            raise ValueError(f"Insufficient extracted text in {filename}")
        records.append({
            "record_id": f"BSEE-SA-{number:03d}",
            "title": title,
            "source_collection": "BSEE_HISTORICAL_SAFETY_ALERTS",
            "source_url": url,
            "archive_url": ARCHIVE_URL,
            "source_file": filename,
            "source_pdf_sha256": sha256(payload).hexdigest(),
            "source_pages": page_count,
            "source_text": text,
            "retrieved_at": retrieved_at,
            "source_reuse_status": "REVIEW_ONLY; per-item copyright/third-party-content status pending",
            "sif_status": "NOT_ASSIGNED",
            "lsr_tags": [],
            "is_synthetic": False,
            "training_use_status": "PENDING",
        })
    with (output / "source_records.jsonl").open("x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    manifest = {
        "status": "REVIEW_ONLY",
        "source": "BSEE Historical Safety Alerts",
        "archive_url": ARCHIVE_URL,
        "BSEE_copyright_notice": BSEE_NOTICE,
        "retrieved_at": retrieved_at,
        "selected_alerts": len(records),
        "synthetic_records": 0,
        "labels_assigned": 0,
        "training_eligible_records": 0,
        "selection_policy": "Individual-event reports selected for offshore lifting, pressure, well-control, fire, electrical and work-at-height coverage. No source title or topic is a model label.",
        "rights_policy": "BSEE states federal materials generally belong to the public domain but cannot confirm every item. Keep review-only until each report is screened for third-party or restricted material.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.output)
