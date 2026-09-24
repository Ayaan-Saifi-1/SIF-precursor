"""Fixture-only tests: no real incident labels or model inference."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from ml.dataset_io import read_dataset_rows

from scripts.pilot_dataset import (
    FIELDS, audit, export_sif, parse_pages, review_rows,
)


def event(narrative="A load fell. Nobody was underneath.", primary="Line of fire"):
    return f"""DATE: 09 May 2024
COUNTRY: Ghana
FUNCTION: Production
CAUSE: Dropped objects
ACTIVITY: Unspecified – other
PRIMARY LIFE-SAVING RULE: {primary}
SECONARY LIFE-SAVING RULE: Work authorization
NARRATIVE:
{narrative}
WHAT WENT WRONG:
Inspection was incomplete.
CORRECTIVE ACTIONS AND RECOMMENDATIONS:
Inspect the fixtures.
CAUSAL FACTORS:
PROCESS (CONDITIONS): Maintenance
"""


class ParserTests(unittest.TestCase):
    def test_trainer_preserves_multiline_quoted_narratives(self):
        raw = '\ufeffdescription,label\r\n"A worker inspected\n\"\"the pump\"\", then stopped.",1\r\n'.encode('utf-8')
        rows = read_dataset_rows(raw)
        self.assertEqual(rows[0]['description'], 'A worker inspected\n"the pump", then stopped.')
        self.assertEqual(rows[0]['label'], '1')

    def test_page_continuation_and_no_exposure_inference(self):
        text = event()
        first, second = text.split("Nobody")
        records = parse_pages([
            first + "\n2024 safety data – High potential event reports\n5\nAFRICA ONSHORE",
            "AFRICA ONSHORE\nNobody" + second,
            "This page is intentionally blank\n119",
            "For the full analysis of 2024 results,\ncontact details",
        ], "TEST")
        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual((r["page_start"], r["page_end"]), (1, 2))
        self.assertEqual(r["source_tags"], ["Line of Fire", "Work Authorisation"])
        self.assertNotIn("Inspection", r["narrative"])
        self.assertNotIn("contact details", r["causal_factors"])
        self.assertNotIn("AFRICA", r["narrative"])
        row = review_rows(records, {"source_url": "fixture", "pdf_sha256": "abc"})[0]
        self.assertEqual(row["actual_exposure"], "")
        self.assertEqual(row["label"], "")
        self.assertEqual(row["lsr_tags"], "")
        self.assertEqual(audit([row])["sif_training_eligible"], 0)

    def test_no_applicable_rule_does_not_become_sif_negative(self):
        text = event(primary="Other issue – no applicable rule").replace(
            "SECONARY LIFE-SAVING RULE: Work authorization\n", "")
        r = parse_pages([text], "TEST")
        row = review_rows(r, {"source_url": "fixture", "pdf_sha256": "abc"})[0]
        self.assertEqual(row["source_tags"], "[]")
        self.assertEqual(row["source_sif_status"], "PUBLISHER_HIGH_POTENTIAL")
        self.assertEqual(row["label"], "")

    def test_unknown_rules_and_missing_sections_fail(self):
        with self.assertRaisesRegex(ValueError, "Unrecognised"):
            parse_pages([event(primary="Unknown future category")], "TEST")
        with self.assertRaisesRegex(ValueError, "Incomplete event"):
            parse_pages([event().split("WHAT WENT WRONG")[0]], "TEST")

    def test_duplicate_narratives_share_group(self):
        records = parse_pages([event(), event()], "TEST")
        self.assertEqual(records[0]["event_group"], records[1]["event_group"])
        self.assertNotEqual(records[0]["record_id"], records[1]["record_id"])


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.records = parse_pages([event(narrative=f"Fixture incident number {i}.") for i in range(40)], "TEST")
        self.rows = review_rows(self.records, {"source_url": "fixture", "pdf_sha256": "abc"})
        for i, row in enumerate(self.rows):
            row.update(label=str(i % 2), hse_reviewed="true", reviewer="TEST FIXTURE",
                       reviewed_at="2026-09-19", label_reason="Fixture only",
                       training_use_status="CLEARED", training_use_basis="Fixture only",
                       report_type="Incident", split=("train", "calibration", "validation", "test")[i // 10])
        self.source = self.root / "sources.jsonl"
        self.source.write_text("\n".join(json.dumps(r) for r in self.records), encoding="utf-8")

    def run_export(self):
        path = self.root / "review.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.rows)
        return export_sif(path, self.source, self.root / "export.csv")

    def test_export_has_no_publisher_labels_or_hindsight(self):
        result = self.run_export()
        self.assertEqual(result["exported"], 40)
        with (self.root / "export.csv").open(encoding="utf-8", newline="") as f:
            exported = list(csv.DictReader(f))
        self.assertNotIn("source_tags", exported[0])
        self.assertNotIn("source_primary_rule", exported[0])
        self.assertEqual(exported[0]["description"], "Fixture incident number 0.")

    def test_unreviewed_and_uncleared_rows_fail(self):
        self.rows[0]["hse_reviewed"] = "false"
        with self.assertRaisesRegex(ValueError, "hse_reviewed"):
            self.run_export()
        self.rows[0]["hse_reviewed"] = "true"
        self.rows[0]["training_use_status"] = "PENDING"
        with self.assertRaisesRegex(ValueError, "training_use_status"):
            self.run_export()

    def test_cross_split_event_and_positive_only_data_fail(self):
        self.rows[10]["event_group"] = self.rows[0]["event_group"]
        with self.assertRaisesRegex(ValueError, "crosses"):
            self.run_export()
        self.rows[10]["event_group"] = self.records[10]["event_group"]
        for row in self.rows:
            row["label"] = "1"
        with self.assertRaisesRegex(ValueError, "both classes"):
            self.run_export()

    def test_modified_input_requires_recorded_reason(self):
        self.rows[0]["description"] = "Edited input."
        with self.assertRaisesRegex(ValueError, "input_edit_reason"):
            self.run_export()


if __name__ == "__main__":
    unittest.main()
