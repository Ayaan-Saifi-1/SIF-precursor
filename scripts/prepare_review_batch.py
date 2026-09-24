"""Build a source-backed, unlabelled HSE review batch. No model inference."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from difflib import SequenceMatcher
import io
import json
from pathlib import Path
import re
import zipfile

from scripts.pilot_dataset import FIELDS, digest, normalize, eligibility_errors

IHM_URL = "https://www.kaggle.com/datasets/ihmstefanini/industrial-safety-and-health-analytics-database"
IHM_MEMBER = "IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv"
IMCA_KEEP = {"SF-10-21.pdf": [2, 3, 4, 5], "SF-15-23.pdf": [1, 3, 4], "SF-26-22.pdf": [1, 2, 3, 5]}
EXTRA = ["source_collection", "source_record_id", "source_actual_severity",
         "source_potential_severity", "source_critical_risk", "source_domain",
         "source_file", "source_row_number", "selection_reason"]

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def write_csv(path, rows, fields):
    with path.open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def blank_review(rid, narrative, source, group, url):
    row = dict.fromkeys(FIELDS + EXTRA, "")
    row.update(report_id=rid, description=narrative, source_collection=source,
               source_url=url, source_tags="[]", source_sif_status="NOT_ASSIGNED",
               event_group=group, hse_reviewed="false", tag_reviewed="false",
               is_synthetic="false", training_use_status="PENDING")
    return row

def ihm_records(raw):
    meta = json.loads((raw / "ihm_metadata.json").read_text(encoding="utf-8"))
    publisher = next(x for x in meta if x.get("ref") == "ihmstefanini/industrial-safety-and-health-analytics-database")
    if publisher.get("licenseName") != "CC0: Public Domain":
        raise ValueError("Recheck changed IHM source licence.")
    with zipfile.ZipFile(raw / "ihm.zip") as z:
        payload = z.read(IHM_MEMBER)
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    result = []
    for index, value in enumerate(rows, 1):
        narrative = value["Description"]
        if not narrative.strip():
            raise ValueError("Missing IHM narrative")
        rid = f"IHM-2018-{index:04d}"
        group = "narrative-" + digest(normalize(narrative))
        review = blank_review(rid, narrative, "IHM", group, IHM_URL)
        review.update(source_record_id=value.get("", ""), source_file=IHM_MEMBER,
                      source_row_number=index, source_domain=value["Industry Sector"],
                      source_actual_severity=value["Accident Level"],
                      source_potential_severity=value["Potential Accident Level"],
                      source_critical_risk=value["Critical Risk"],
                      source_event_date=value["Data"],
                      training_use_status="CLEARED",
                      training_use_basis="Publisher Kaggle metadata: CC0: Public Domain; " + IHM_URL)
        original = dict(record_id=rid, narrative=narrative, event_group=group,
                        source_collection="IHM", source_url=IHM_URL, source_row_number=index,
                        narrative_sha256=digest(narrative), source_file=IHM_MEMBER,
                        source_file_sha256=digest(payload), source_values=value)
        result.append((review, original))
    return result

def imca_records(raw):
    import pdfplumber
    downloads = {r["file"]: r for r in json.loads((raw / "downloads.json").read_text()) if "error" not in r}
    result, excluded = [], []
    for filename, keep in IMCA_KEEP.items():
        events, current = {}, None
        with pdfplumber.open(raw / filename) as pdf:
            for page_number, page in enumerate(pdf.pages, 1):
                # Body/title text uses 11/12 point. Rule boxes, footer and figure
                # labels are smaller; cover masthead and legal header are excluded.
                body = page.filter(lambda o: o.get("object_type") == "char"
                    and 10.8 <= o.get("size", 0) <= 12.6
                    and o["top"] >= 50 and o["bottom"] <= 790
                    and not (filename == "SF-10-21.pdf" and page_number == 3
                             and 745 <= o["top"] <= 780 and "Italic" in o.get("fontname", ""))
                    and not (filename == "SF-26-22.pdf" and page_number == 4
                             and 330 <= o["top"] <= 363 and "Italic" in o.get("fontname", "")))
                lines = body.extract_text_lines(layout=False)
                boundaries = []
                for line in lines:
                    match = re.match(r"^([1-5])\s+(.+)", line["text"])
                    if match:
                        current = int(match[1])
                        if current in events:
                            raise ValueError("Repeated IMCA event heading")
                        events[current] = {"title": match[2], "lines": [], "rule_box_text": [], "pages": []}
                        boundaries.append((line["top"], current))
                    if current is not None:
                        events[current]["lines"].append(line["text"])
                        if page_number not in events[current]["pages"]:
                            events[current]["pages"].append(page_number)
                # Assign small rule-box text to its actual event on this page.
                segments = []
                if boundaries:
                    first_top = boundaries[0][0]
                    if first_top > 50:
                        previous = boundaries[0][1] - 1
                        if previous in events:
                            segments.append((50, first_top, previous))
                    for index, (top, number) in enumerate(boundaries):
                        bottom = boundaries[index + 1][0] if index + 1 < len(boundaries) else 760
                        segments.append((top, bottom, number))
                elif current is not None:
                    segments.append((50, 760, current))
                for top, bottom, number in segments:
                    small = page.filter(lambda o: o.get("object_type") == "char"
                        and 5 <= o.get("size", 0) <= 9.3 and o["x0"] >= 390
                        and o["top"] >= top and o["bottom"] <= bottom)
                    events[number]["rule_box_text"].append(small.extract_text() or "")
        if set(events) != {1, 2, 3, 4, 5}:
            raise ValueError(f"Unexpected section structure in {filename}: {list(events)}")
        for number, event in events.items():
            if number not in keep:
                excluded.append({"file": filename, "section": number, "title": event["title"],
                                 "reason": "Multi-incident/aggregate section; avoid representing as one event."})
                continue
            lines = event["lines"]
            start = next(i for i, s in enumerate(lines) if re.match(r"^What happened\??$", s))
            end = next((i for i in range(start + 1, len(lines))
                        if re.match(r"^(What (went|was|were|caused)|Actions|Lessons|Our member|Members may)", lines[i])),
                       len(lines))
            narrative = "\n".join(lines[start + 1:end]).strip()
            if len(narrative) < 100:
                raise ValueError(f"Short IMCA extraction: {filename}/{number}")
            raw_rules = "\n".join(event["rule_box_text"])
            words = set(re.findall(r"[a-z]+", raw_rules.casefold()))
            tags = []
            if {"applicable", "rule", "saving"}.issubset(words):
                for tag in ("Bypassing Safety Controls", "Energy Isolation", "Line of Fire", "Safe Mechanical Lifting",
                            "Confined Space", "Driving", "Hot Work", "Work Authorisation", "Working at Height"):
                    if set(tag.lower().split()).issubset(words):
                        tags.append(tag)
            rid = "IMCA-" + filename.replace("SF-", "").replace(".pdf", "") + f"-{number:02d}"
            group = "narrative-" + digest(normalize(narrative))
            url = downloads[filename]["url"]
            review = blank_review(rid, narrative, "IMCA", group, url)
            review.update(source_record_id=f"{filename} section {number}",
                          source_file=filename, source_domain="OFFSHORE_MARINE",
                          source_pdf_sha256=downloads[filename]["sha256"],
                          source_page_start=min(event["pages"]), source_page_end=max(event["pages"]),
                          source_tags=json.dumps(tags),
                          source_primary_rule=tags[0] if tags else "",
                          source_secondary_rule=tags[1] if len(tags) > 1 else "")
            # Do not claim sidebar order is a publisher primary/secondary ranking.
            review["source_primary_rule"] = review["source_secondary_rule"] = ""
            original = dict(record_id=rid, narrative=narrative, event_group=group,
                            source_collection="IMCA", source_url=url, source_file=filename,
                            source_pdf_sha256=downloads[filename]["sha256"], source_pages=event["pages"],
                            source_section=number, title=event["title"], source_tags=tags,
                            source_rule_box_text=raw_rules, narrative_sha256=digest(narrative),
                            source_section_text="\n".join(lines),
                            extraction="pdfplumber 11/12-point body text; What happened section only. Verified figure-caption regions excluded on SF-10-21 page 3 and SF-26-22 page 4. Whitespace reconstructed; wording not rewritten.",
                            source_reuse_status="LOCAL_REVIEW_ONLY; training permission pending",
                            publication_date_not_event_date=True)
            result.append((review, original))
    return result, excluded

def load_existing(path, name):
    rows = list(csv.DictReader((path / "review.csv").open(encoding="utf-8-sig", newline="")))
    originals = {r["record_id"]: r for r in map(json.loads, (path / "source_records.jsonl").read_text(encoding="utf-8").splitlines())}
    result = []
    for row in rows:
        original = originals[row["report_id"]]
        if row["description"] != original["narrative"]:
            raise ValueError("Existing corpus narrative differs from original.")
        row = dict(row, source_collection=name)
        original = dict(original, source_collection=name)
        result.append((row, original))
    return result

def shingles(text):
    words = re.findall(r"\w+", text.casefold())
    return set(zip(words, words[1:], words[2:]))

def build(root, collection, output):
    if output.exists():
        raise ValueError("Output exists; do not overwrite review work.")
    raw = collection / "raw"
    imca, excluded = imca_records(raw)
    pairs = (load_existing(root / "data/pilot/iogp-2024sh", "IOGP")
             + load_existing(root / "data/pilot/zenodo-21108212/msha-review-v1", "MSHA")
             + ihm_records(raw) + imca)
    groups = defaultdict(list)
    for row, original in pairs:
        assert row["is_synthetic"] == "false"
        assert row["description"] == original["narrative"]
        groups[normalize(row["description"])].append((row, original))
    duplicates, conflicts, unique = [], set(), []
    for text, group in groups.items():
        ids = [row["report_id"] for row, _ in group]
        # Choose one representative for sampling; preserve every original source row.
        unique.append(group[0])
        if len(group) > 1:
            source_labels = {(r.get("source_actual_severity", ""), r.get("source_potential_severity", "")) for r, _ in group}
            conflict = len(source_labels) > 1
            if conflict:
                conflicts.update(ids)
            duplicates.append({"record_ids": ids, "source_label_conflict": conflict,
                               "source_actual_potential_pairs": sorted(source_labels)})
    near, flagged = [], set()
    sets = [shingles(r["description"]) for r, _ in unique]
    for i in range(len(unique)):
        if not sets[i]:
            continue
        for j in range(i):
            common = len(sets[i] & sets[j])
            if not common:
                continue
            similarity = common / len(sets[i] | sets[j])
            if similarity >= 0.50:
                a, b = unique[i][0], unique[j][0]
                near.append({"report_a": a["report_id"], "report_b": b["report_id"],
                             "trigram_jaccard": round(similarity, 4), "status": "UNRESOLVED"})
                flagged.update((a["report_id"], b["report_id"]))
    eligible = [(r, o) for r, o in unique if r["report_id"] not in conflicts | flagged]
    selected, selected_ids, event_groups = [], set(), set()
    def take(pool, count, reason):
        taken = 0
        for row, original in sorted(pool, key=lambda pair: digest("HSE-BATCH-001|" + pair[0]["report_id"])):
            if row["report_id"] in selected_ids or row["event_group"] in event_groups:
                continue
            selected.append((dict(row, selection_reason=reason), original))
            selected_ids.add(row["report_id"])
            event_groups.add(row["event_group"])
            taken += 1
            if taken == count:
                return
        if taken < count:
            raise ValueError(f"Insufficient records for {reason}: {taken}/{count}")
    # Source level only prioritizes review. It never assigns a target label.
    for level, count in (("I", 10), ("II", 10), ("III", 8), ("IV", 8), ("V", 3), ("VI", 1)):
        take([(r, o) for r, o in eligible if r["source_collection"] == "IHM"
              and r.get("source_potential_severity") == level], count, "Source potential level " + level + "; not a SIF label")
    iogp = [(r, o) for r, o in eligible if r["source_collection"] == "IOGP"]
    for tag in ("Confined Space", "Driving", "Hot Work", "Working at Height", "Energy Isolation",
                "Bypassing Safety Controls", "Work Authorisation", "Safe Mechanical Lifting", "Line of Fire"):
        take([(r, o) for r, o in iogp if tag in json.loads(r["source_tags"])], 1, "Publisher tag coverage: " + tag)
    take(iogp, 26, "Oil-and-gas source diversity")
    take([(r, o) for r, o in eligible if r["source_collection"] == "IMCA"], 11, "Single-incident offshore source report")
    take([(r, o) for r, o in eligible if r["source_collection"] == "MSHA"], 14, "Mining domain-transfer comparison")
    selected.sort(key=lambda pair: digest("BLIND-ORDER-001|" + pair[0]["report_id"]))
    assert len(selected) == 100
    assert len({normalize(r["description"]) for r, _ in selected}) == 100
    assert all(eligibility_errors(r) for r, _ in selected)
    assert all(not r["label"] and not r["lsr_tags"] and not r["split"] for r, _ in selected)
    output.mkdir(parents=True)
    write_csv(output / "adjudication.csv", [r for r, _ in selected], FIELDS + EXTRA)
    fields = ["review_item_id", "description", "label", "lsr_tags", "actual_exposure",
              "exposure_evidence", "barrier_state", "barrier_evidence", "label_reason",
              "information_missing", "reviewer", "reviewed_at", "review_notes"]
    blinded = [dict.fromkeys(fields, "") for _ in selected]
    key = []
    for index, ((row, _), blind) in enumerate(zip(selected, blinded), 1):
        item = f"HSE-001-{index:03d}"
        blind.update(review_item_id=item, description=row["description"])
        key.append({"review_item_id": item, "report_id": row["report_id"],
                    "source_collection": row["source_collection"], "source_url": row["source_url"],
                    "selection_reason": row["selection_reason"]})
    write_csv(output / "reviewer_A.csv", blinded, fields)
    write_csv(output / "reviewer_B.csv", blinded, fields)
    write_csv(output / "review_key.csv", key, list(key[0]))
    with (output / "source_records.jsonl").open("x", encoding="utf-8") as f:
        for _, original in selected:
            f.write(json.dumps(original, ensure_ascii=False) + "\n")
    # Full source pool stays outside the blinded first-pass review.
    with (output / "collected_source_records.jsonl").open("x", encoding="utf-8") as f:
        for row, original in pairs:
            f.write(json.dumps(dict(original, intake_metadata={k: row.get(k, "") for k in EXTRA}), ensure_ascii=False) + "\n")
    write_csv(output / "collected_review.csv", [r for r, _ in pairs], FIELDS + EXTRA)
    write_json(output / "duplicates.json", duplicates)
    write_csv(output / "near_duplicate_candidates.csv", near, ["report_a", "report_b", "trigram_jaccard", "status"])
    manifest = {
        "status": "REVIEW_ONLY", "batch_id": "HSE-001",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_records": len(pairs), "exact_unique_narratives": len(unique),
        "source_counts": dict(Counter(r["source_collection"] for r, _ in pairs)),
        "selected_records": len(selected),
        "selected_sources": dict(Counter(r["source_collection"] for r, _ in selected)),
        "source_duplicate_groups": len(duplicates), "conflicting_source_label_record_ids": sorted(conflicts),
        "near_duplicate_candidate_pairs": len(near), "near_duplicate_policy": "3-word shingle Jaccard >= 0.50; flags for review, not proof; flagged representatives excluded from batch.",
        "imca_excluded_aggregate_sections": excluded,
        "selected_source_tag_coverage": dict(Counter(t for r, _ in selected for t in json.loads(r["source_tags"]))),
        "sif_training_eligible": 0, "labels_assigned": 0, "hse_reviewed": 0,
        "synthetic_records": 0, "selection_is_representative": False,
        "source_label_policy": "Source IHM levels and IMCA/IOGP tags are preserved but never converted into reviewed target labels.",
        "review_blinding": "Reviewer A/B files omit source levels, tags, record IDs and selection reason. Narrative itself can disclose outcome/source; blinding is partial.",
        "limits": ["Uncertain SIF cases are to be identified by reviewers, not prelabelled by the agent.",
                   "No original report sources modified; no app DB/model changes.",
                   "IMCA training reuse pending. IHM publisher CC0 recorded.",
                   "Near-duplicate checks cannot prove distinct events. HSE event grouping review required."],
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.root, args.collection, args.output)

