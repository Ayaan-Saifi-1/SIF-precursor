"""Collect public IADC alerts as source-backed, unlabelled review material.

The collector deliberately preserves the original public feed and does not infer
SIF status, life-saving-rule tags, or target labels.  IADC material is marked
REVIEW_ONLY until training reuse permission is recorded.
"""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.request import Request, urlopen


FEED_URL = (
    "https://safetyalerts.iadc.org/api/api/SafetyAlerts/Published/Public"
    "?companyName=safetyalerts"
)
PUBLIC_PAGE = "https://safetyalerts.iadc.org/web/public-published-alerts"


class TextOnly(HTMLParser):
    """Extract visible text while retaining paragraph and list boundaries."""

    BLOCKS = {"p", "br", "li", "div", "h1", "h2", "h3", "h4", "ol", "ul"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        return "\n".join(
            " ".join(line.split())
            for line in "".join(self.parts).splitlines()
            if line.strip()
        ).strip()


def digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def html_to_text(value):
    parser = TextOnly()
    parser.feed(value or "")
    parser.close()
    return parser.text()


def alert_url(alert):
    return (
        f"{PUBLIC_PAGE}/view/{alert['detailID']}"
        f"/year/{alert['alertYearCode']}/code/{alert['alertYearCodeID']}"
    )


def fetch(url):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ASCENSION-review-intake/1.0"})
    with urlopen(request, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f"IADC returned HTTP {response.status}")
        return response.read()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def collect(output):
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    raw = fetch(FEED_URL)
    alerts = json.loads(raw)
    if not isinstance(alerts, list) or not alerts:
        raise ValueError("IADC public feed was empty or changed format")
    ids = [item.get("safetyAlertID") for item in alerts]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("IADC feed contains missing or duplicate safetyAlertID values")

    output.mkdir(parents=True)
    (output / "published_alerts.json").write_bytes(raw)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    records = []
    for alert in alerts:
        narrative = html_to_text(alert.get("whatHappened", ""))
        if not narrative:
            continue
        tags = [answer.get("optionText", "") for answer in alert.get("answers", []) if answer.get("optionText")]
        record_id = f"IADC-{alert['safetyAlertID']}"
        source_url = alert_url(alert)
        records.append({
            "record_id": record_id,
            "narrative": narrative,
            "narrative_sha256": digest(narrative),
            "event_group": "narrative-" + digest(" ".join(narrative.casefold().split())),
            "source_collection": "IADC_PUBLIC_ALERTS",
            "source_record_id": str(alert["safetyAlertID"]),
            "source_url": source_url,
            "source_feed_url": FEED_URL,
            "title": alert.get("title", ""),
            "operation_category": alert.get("operationCategory", ""),
            "is_land": alert.get("isLand"),
            "source_incident_date": alert.get("incidentDate", ""),
            "source_published_on": alert.get("publishedOn", ""),
            "source_tags": tags,
            "contributing_factors_html": alert.get("contributingFactors", ""),
            "lessons_learned_html": alert.get("lessonsLearned", ""),
            "retrieved_at": retrieved_at,
            "source_reuse_status": "REVIEW_ONLY; training permission pending",
            "sif_status": "NOT_ASSIGNED",
            "lsr_tags": [],
            "is_synthetic": False,
            "training_use_status": "PENDING",
            "note": "Publisher tags and outcomes are source metadata, not ASCENSION labels.",
        })
    if not records:
        raise ValueError("No IADC records contained a whatHappened narrative")
    with (output / "source_records.jsonl").open("x", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    fields = [
        "record_id", "title", "narrative", "source_url", "operation_category", "is_land",
        "source_incident_date", "source_published_on", "source_tags", "sif_status", "lsr_tags",
        "is_synthetic", "training_use_status", "source_reuse_status",
    ]
    with (output / "review.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in records:
            row = dict(row, source_tags=json.dumps(row["source_tags"]), lsr_tags="[]")
            writer.writerow(row)
    manifest = {
        "status": "REVIEW_ONLY",
        "source": "IADC public Safety Alert System",
        "catalogue": PUBLIC_PAGE,
        "feed_url": FEED_URL,
        "retrieved_at": retrieved_at,
        "feed_sha256": sha256(raw).hexdigest(),
        "feed_alerts": len(alerts),
        "records_with_narrative": len(records),
        "records_without_narrative": len(alerts) - len(records),
        "synthetic_records": 0,
        "labels_assigned": 0,
        "training_eligible_records": 0,
        "narrative_policy": "whatHappened only; contributing factors and lessons retained separately as source evidence.",
        "label_policy": "No source field, publisher tag, injury outcome, stated potential, or missing tag is an ASCENSION label.",
        "rights_policy": "Do not export for training until IADC confirms model-training reuse permission.",
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.output)
