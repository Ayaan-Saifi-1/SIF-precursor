"""Prepare real MSHA-derived narratives for review; never infer safety labels."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import heapq
import io
import json
from pathlib import Path
import re
import zipfile
import csv

from scripts.pilot_dataset import FIELDS, digest, normalize, eligibility_errors

SOURCE_URL = "https://zenodo.org/records/21108212"
EXPECTED_MD5 = "03035e895c185fdec253aaa3ed93a8ab"
MEMBER = "dynamicNarrativeClimateData/coalMining/events.parquet"
COLUMNS = [
    "mine_id", "document_no", "eid", "accident_date", "commodity", "narrative",
    "degree_injury", "fatality", "accident_only", "classification", "activity",
]
# Retrieval buckets only: these are NOT SIF or life-saving-rule labels.
PATTERNS = {
    "lifting": r"\b(crane|hoist|rigging|sling|suspended load)\b",
    "stored_energy": r"\b(lockout|tagout|loto|deenergized|de-energized|isolation|stored energy)\b",
    "electrical": r"\b(electrical|electrocution|energized|voltage|arc flash)\b",
    "pressure": r"\b(pressurized|pressure|hydraulic|compressed air)\b",
    "hot_work": r"\b(welding|welder|torch|hot work|cutting torch)\b",
    "confined_space": r"\b(confined space|oxygen|asphyxiation|hydrogen sulfide|h2s|tank entry)\b",
    "height": r"\b(scaffold|ladder|harness|fall protection|elevated platform)\b",
    "vehicles": r"\b(truck|vehicle|forklift|loader|bulldozer)\b",
    "moving_equipment": r"\b(conveyor|rotating|pinch point|caught between|caught in)\b",
}

def file_hash(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def source_event_group(row):
    # Conservative: same mine/date may include several independent events.
    # Keep them together rather than letting multiple injury reports leak across splits.
    value = str(row.get("accident_date") or "")[:10]
    if row.get("mine_id") and value:
        return "MSHA-mine-date-" + digest(str(row["mine_id"]) + "|" + value)[:24]
    return "MSHA-document-" + str(row["document_no"])

def prepare(archive, output, per_bucket=30):
    import pyarrow.parquet as pq

    if per_bucket < 1 or per_bucket > 100:
        raise ValueError("per_bucket must be between 1 and 100.")
    if output.exists():
        raise ValueError("Output already exists; never overwrite reviewer work.")
    if file_hash(archive, "md5") != EXPECTED_MD5:
        raise ValueError("Archive does not match the publisher checksum.")
    archive_sha = file_hash(archive)
    regexes = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
    buckets = list(regexes) + ["unfiltered_comparison"]
    capacity = per_bucket * len(buckets)
    pools = {k: [] for k in buckets}
    counts, commodities, years, text_counts = Counter(), Counter(), Counter(), Counter()
    total = usable = 0
    with zipfile.ZipFile(archive) as z:
        # Read one explicitly named member; never extract arbitrary archive paths.
        payload = z.read(MEMBER)
    member_sha = digest(payload)
    source = pq.ParquetFile(io.BytesIO(payload))
    missing = set(COLUMNS) - set(source.schema_arrow.names)
    if missing:
        raise ValueError(f"Source schema changed: missing {sorted(missing)}")
    for batch in source.iter_batches(batch_size=4096, columns=COLUMNS):
        for row in batch.to_pylist():
            total += 1
            commodities[str(row.get("commodity"))] += 1
            years[str(row.get("accident_date") or "")[:4]] += 1
            narrative = row.get("narrative")
            if (not isinstance(narrative, str) or len(narrative.strip()) < 40
                    or not row.get("document_no") or not row.get("eid")):
                continue
            usable += 1
            text_hash = digest(normalize(narrative))
            text_counts[text_hash] += 1
            matches = [k for k, pattern in regexes.items() if pattern.search(narrative)]
            counts.update(matches)
            rank = int(digest("ASCENSION-MSHA-review-v1|" + row["eid"]), 16)
            row["_source_row"] = total
            row["_text_hash"] = text_hash
            row["_event_group"] = source_event_group(row)
            row["_matched_buckets"] = matches
            for key in matches + ["unfiltered_comparison"]:
                item = (-rank, -total, row)
                pool = pools[key]
                if len(pool) < capacity:
                    heapq.heappush(pool, item)
                elif item[:2] > pool[0][:2]:
                    heapq.heapreplace(pool, item)

    selected, seen_ids, seen_text, seen_groups = [], set(), set(), set()
    for key in buckets:
        taken = 0
        for _, _, row in sorted(pools[key], reverse=True):
            if (row["eid"] in seen_ids or row["_text_hash"] in seen_text
                    or row["_event_group"] in seen_groups):
                continue
            chosen = dict(row, _selection_bucket=key)
            selected.append(chosen)
            seen_ids.add(row["eid"])
            seen_text.add(row["_text_hash"])
            seen_groups.add(row["_event_group"])
            taken += 1
            if taken == per_bucket:
                break
    if not selected:
        raise ValueError("No usable narratives.")
    originals, reviews = [], []
    for source_row in selected:
        narrative = source_row["narrative"]
        rid = "MSHA-" + source_row["eid"]
        source_values = {k: v.isoformat() if isinstance(v, datetime) else v
                         for k, v in source_row.items() if not k.startswith("_")}
        originals.append({
            "record_id": rid, "narrative": narrative,
            "narrative_sha256": digest(narrative),
            "event_group": source_row["_event_group"],
            "source_url": SOURCE_URL, "source_member": MEMBER,
            "source_row_number": source_row["_source_row"],
            "source_values": source_values,
            "selection_bucket": source_row["_selection_bucket"],
            "matched_retrieval_buckets": source_row["_matched_buckets"],
            "is_synthetic": False,
        })
        row = dict.fromkeys(FIELDS, "")
        row.update(
            report_id=rid, description=narrative,
            source_event_date=str(source_row["accident_date"] or "")[:10],
            source_country="United States",
            source_activity=source_row.get("activity") or "",
            source_tags="[]", source_sif_status="NOT_LABELLED_BY_SOURCE",
            source_url=SOURCE_URL, event_group=source_row["_event_group"],
            hse_reviewed="false", tag_reviewed="false", is_synthetic="false",
            training_use_status="PENDING",
            source_domain="MINING", source_commodity=source_row["commodity"],
            source_record_id=source_row["document_no"],
            source_archive_sha256=archive_sha, source_member=MEMBER,
            source_row_number=source_row["_source_row"],
            selection_bucket=source_row["_selection_bucket"],
        )
        reviews.append(row)
    assert all(eligibility_errors(row) for row in reviews)
    assert all(not row["label"] and not row["lsr_tags"] and not row["split"] for row in reviews)
    assert len({r["description"] for r in reviews}) == len(reviews)
    manifest = {
        "schema_version": "ascension-msha-review-1",
        "source_url": SOURCE_URL, "source_doi": "10.5281/zenodo.21108212",
        "attribution": "Rosen, Michael; Kilcullen, Molly; Zhu, Yuxin (2026). Safety event reporting narratives, safety outcomes, and operational data across four industries. Zenodo.",
        "publisher_license": "CC-BY-4.0",
        "source_archive_md5": EXPECTED_MD5, "source_archive_sha256": archive_sha,
        "source_member": MEMBER, "source_member_sha256": member_sha,
        "source_rows": total, "usable_narrative_rows": usable,
        "source_commodity_counts": dict(commodities), "source_year_counts": dict(sorted(years.items())),
        "source_exact_duplicate_rows_beyond_first": sum(n - 1 for n in text_counts.values()),
        "retrieval_match_counts": dict(counts),
        "selected_records": len(reviews),
        "selected_buckets": dict(Counter(r["selection_bucket"] for r in reviews)),
        "selected_commodities": dict(Counter(r["source_commodity"] for r in reviews)),
        "selection": "Deterministic SHA-256 order of source eid; up to N per retrieval bucket, then unfiltered comparison. Selected narratives and mine/date groups are unique.",
        "per_bucket": per_bucket, "retrieval_patterns": PATTERNS,
        "grouping": "Conservative mine/date group; document fallback. Cross-source and near-duplicate review still required.",
        "status": "REVIEW_ONLY", "hse_reviewed": 0, "sif_training_eligible": 0,
        "training_use_status": "PENDING",
        "training_use_note": "Publisher CC-BY-4.0 recorded; confirm underlying-source terms, attribution and intended use before clearance.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Mining domain transfer; not oil-and-gas operational data.",
            "The coalMining table also contains metal/non-metal records.",
            "No SIF, life-saving-rule, exposure or barrier labels inferred.",
            "Retrieval bucket names are not safety classifications.",
            "Unfiltered comparison is not a labelled negative class.",
            "Outcomes remain in source_values, not added to prediction text.",
            "Narratives themselves may contain outcome leakage or personal information; review before training.",
            "Sample is intentionally diversified, not representative of incident prevalence.",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with (output / "source_records.jsonl").open("w", encoding="utf-8") as f:
        for row in originals:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    extra = [k for k in reviews[0] if k not in FIELDS]
    with (output / "review.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS + extra)
        writer.writeheader()
        writer.writerows(reviews)
    (output / "README.md").write_text(
        "# MSHA-derived real incident review sample\n\n"
        f"Selected {len(reviews)} verbatim narratives from {total:,} mining-table rows.\n\n"
        "Source: " + SOURCE_URL + "\n\n" + manifest["attribution"] + "\n\n"
        "Publisher licence: CC BY 4.0. Status: REVIEW_ONLY; no expert labels or trained model.\n\n"
        "Use review.csv with docs/DATASET_PILOT.md. source_records.jsonl preserves "
        "source IDs, archive row numbers and source outcome fields separately. "
        "The original archive and publisher metadata are in the parent directory.\n\n"
        "Retrieval buckets prioritize annotation only; they are not life-saving tags. "
        "The unfiltered comparison bucket is not a negative class. Mining records "
        "must be assessed for transfer to oil-and-gas use.\n\n"
        "Review for privacy, prediction-time leakage, cross-source duplicates, "
        "attribution and source terms before assigning labels or exporting data. "
        "Do not use the entire CSV or JSON as model input.\n", encoding="utf-8")
    return {k: manifest[k] for k in (
        "source_rows", "usable_narrative_rows", "source_commodity_counts",
        "source_exact_duplicate_rows_beyond_first", "selected_records",
        "selected_buckets", "selected_commodities", "status", "sif_training_eligible")}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-bucket", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.output, args.per_bucket), indent=2))

if __name__ == "__main__":
    main()

