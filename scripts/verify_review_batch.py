"""Verify prepared review data against source artifacts; never writes model data."""
import csv
import io
import json
import re
from pathlib import Path
import zipfile
from pypdf import PdfReader
from scripts.pilot_dataset import normalize, digest, export_sif, TAGS

def verify(p, raw):
    read = lambda name: list(csv.DictReader((p / name).open(encoding="utf-8-sig", newline="")))
    a, b, master, key = map(read, ("reviewer_A.csv", "reviewer_B.csv", "adjudication.csv", "review_key.csv"))
    originals = {r["record_id"]: r for r in map(json.loads, (p / "source_records.jsonl").read_text(encoding="utf-8").splitlines())}
    manifest = json.loads((p / "manifest.json").read_text())
    assert len(a) == len(b) == len(master) == len(key) == 100 and a == b
    assert len({normalize(r["description"]) for r in a}) == 100
    assert all(not r[k] for r in a for k in r if k not in ("review_item_id", "description"))
    assert not any("source" in k or "selection" in k for k in a[0])
    assert set(manifest["selected_source_tag_coverage"]) == set(TAGS)
    assert not ({r["report_id"] for r in master} & set(manifest["conflicting_source_label_record_ids"]))
    near = read("near_duplicate_candidates.csv")
    flagged = {r[k] for r in near for k in ("report_a", "report_b")}
    assert not ({r["report_id"] for r in master} & flagged)
    for r, k, blind in zip(master, key, a):
        assert r["report_id"] == k["report_id"]
        assert blind["review_item_id"] == k["review_item_id"]
        assert r["description"] == blind["description"] == originals[r["report_id"]]["narrative"]
        assert not r["label"] and not r["lsr_tags"] and not r["split"]
        assert r["hse_reviewed"] == "false" and r["is_synthetic"] == "false"
    clean = lambda s: re.sub(r"\W", "", s.casefold())
    pdf_text = {}
    for r in originals.values():
        if r["source_collection"] == "IMCA":
            assert not any(s in r["narrative"] for s in ("Applicable", "Rule(s)", "What went wrong",
                "Lessons learned", "Inspection taking place", "Power supply extension cable Welding plant"))
            assert r["source_pdf_sha256"] == digest((raw / r["source_file"]).read_bytes())
            if r["source_file"] not in pdf_text:
                pdf_text[r["source_file"]] = clean(" ".join(page.extract_text() or "" for page in PdfReader(raw / r["source_file"]).pages))
            # Independent extractor introduces spaces inside words; compare each
            # narrative line without whitespace/punctuation, preserving characters.
            for line in r["narrative"].splitlines():
                assert clean(line) in pdf_text[r["source_file"]], (r["record_id"], line)
    assert originals["IMCA-26-22-03"]["narrative"].endswith(
        "searching for the leakage source. The crew inspected the quayside to check for spillage.")
    with zipfile.ZipFile(raw / "ihm.zip") as z:
        source = list(csv.DictReader(io.StringIO(z.read(
            "IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv").decode("utf-8-sig"))))
        for r in originals.values():
            if r["source_collection"] == "IHM":
                assert source[r["source_row_number"] - 1]["Description"] == r["narrative"]
    existing = {}
    for name in ("iogp-2024sh", "zenodo-21108212/msha-review-v1"):
        path = p.parent / name / "source_records.jsonl"
        existing.update({r["record_id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())})
    for rid, r in originals.items():
        if r["source_collection"] in ("IOGP", "MSHA"):
            assert r["narrative"] == existing[rid]["narrative"]
    try:
        export_sif(p / "adjudication.csv", p / "source_records.jsonl", p / "must_not_train.csv")
    except ValueError as e:
        assert "hse_reviewed must be true" in str(e)
    else:
        raise AssertionError("Unreviewed data accepted")
    assert not (p / "must_not_train.csv").exists()
    return {"status": "PASS", "records_checked": 100, "source_text_and_hash_checks": True,
            "independent_reviewer_forms_match": True, "source_tag_categories": 9,
            "conflicts_and_flagged_near_duplicates_excluded": True,
            "pdf_caption_and_clipping_regressions": "PASS",
            "unreviewed_training_export_blocked": True, "target_labels_assigned": 0}

if __name__ == "__main__":
    print(json.dumps(verify(Path("data/pilot/hse-review-001-v2"),
        Path("data/pilot/collection-20260919/raw")), indent=2))

