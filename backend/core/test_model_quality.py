"""Guard against scenario leakage and unsafe model/extractor interaction."""
from django.test import SimpleTestCase
from ml.safety_analyzer import analyze


def model_probability(probability, negative_threshold=None):
    def predict(*args):
        return dict(probability=probability, threshold=.7,
                    negative_threshold=negative_threshold, vector=[],
                    encoder_status="READY", classifier_status="READY",
                    model_version="test-fixture")
    return predict


class DecisionInteractionTests(SimpleTestCase):
    def report(self, text):
        return dict(report_id="QUALITY-FIXTURE", description=text,
                    report_type="Near Miss", context={})

    def test_positive_model_does_not_disappear_when_extractor_misses_details(self):
        result=analyze(self.report("An unusual machinery event was reported; supporting details are pending."),
                       inference=model_probability(.95))
        self.assertEqual(result["sif_label"], "SIF_POTENTIAL")
        self.assertTrue(result["missing_information"])
        self.assertTrue(result["review_required"])
        self.assertEqual(result["decision_source"], "MODEL")
        self.assertEqual(result["priority"], "HIGH")

    def test_negative_model_cannot_clear_incomplete_report(self):
        result=analyze(self.report("An unusual machinery event was reported; supporting details are pending."),
                       inference=model_probability(.01, .2))
        self.assertEqual(result["sif_label"], "REVIEW_REQUIRED")
        self.assertTrue(result["review_required"])

    def test_classifier_alone_cannot_turn_classroom_example_into_actual_event(self):
        result=analyze(self.report("A classroom training briefing discussed what to do if a gas detector failed."),
                       inference=model_probability(.99))
        self.assertTrue(result["simulated"])
        self.assertFalse(result["model_applicable"])
        self.assertNotEqual(result["sif_label"], "SIF_POTENTIAL")
        self.assertEqual(result["priority"], "LOW")

    def test_low_probability_never_cancels_hard_gate(self):
        result=analyze(self.report("During operation the PSV was bypassed. An operator beside the separator was exposed."),
                       inference=model_probability(.01, .2))
        self.assertEqual(result["sif_label"], "SIF_POTENTIAL")
        self.assertEqual(result["priority"], "CRITICAL")


class ScenarioSplitTests(SimpleTestCase):
    def test_contrast_pair_cannot_cross_splits(self):
        from ml.development_scenarios import scenarios
        from ml.improve_development_model import validate
        rows=scenarios()
        rows[1]["split"]="test"
        with self.assertRaisesRegex(ValueError,"crosses splits"):
            validate(rows)

    def test_synthetic_examples_cannot_claim_hse_review(self):
        from ml.development_scenarios import scenarios
        from ml.improve_development_model import validate
        rows=scenarios()
        rows[0]["hse_reviewed"]="true"
        with self.assertRaisesRegex(ValueError,"synthetic, unreviewed"):
            validate(rows)

    def test_whitespace_duplicates_rejected(self):
        from ml.development_scenarios import scenarios
        from ml.improve_development_model import validate
        rows=scenarios()
        rows[1]["description"]="  " + rows[0]["description"].upper() + "\n"
        with self.assertRaisesRegex(ValueError,"duplicate narrative"):
            validate(rows)

    def test_extracted_safety_features_have_stable_shape(self):
        from ml.development_model import ExtractedSafetyFeatures
        feature_rows = ExtractedSafetyFeatures().transform([
            "The live cable was proved dead before it was cut.",
            "A worker cut an energised cable and suffered an arc flash.",
        ])
        self.assertEqual(feature_rows.shape, (2, 12))
        self.assertTrue((feature_rows >= 0).all())
        self.assertTrue((feature_rows <= 1).all())

    def test_robustness_transforms_preserve_meaningful_text(self):
        from ml.audit_development_robustness import TRANSFORMS
        source = "A worker stopped before the live cable and notified the crew."
        for name, transform in TRANSFORMS.items():
            with self.subTest(transform=name):
                changed = transform(source)
                self.assertTrue(changed.strip())
                self.assertIn("cable", changed.casefold())

    def test_sentence_max_keeps_the_highest_component_score(self):
        import numpy as np
        from ml.development_model import sentence_max_probability

        class Fixture:
            def predict_proba(self, texts):
                values = [.91 if "live cable" in text else .12 for text in texts]
                return np.asarray([[1 - value, value] for value in values])

        score = sentence_max_probability(
            Fixture(), "Shift entry received. A person cut a live cable. Supervisor notified."
        )
        self.assertEqual(score, .91)


class DevelopmentArtifactTests(SimpleTestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from ml import sif_classifier
        self.module=sif_classifier
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.directory=self.root/"development"
        self.directory.mkdir()
        for name, value in (("ARTIFACT_DIR",self.root/"production"),
                            ("DEVELOPMENT_ARTIFACT_DIR",self.directory)):
            patcher=patch.object(sif_classifier,name,value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.module.load_classifier.cache_clear()
        self.addCleanup(self.module.load_classifier.cache_clear)

    def make_manifest(self, **extra):
        import json
        record=dict(status="SYNTHETIC_DEVELOPMENT_ONLY",production_eligible=False,
                    development_release_eligible=True,threshold=.7,artifact_sha256="invalid")
        record.update(extra)
        (self.directory/"manifest.json").write_text(json.dumps(record))
        (self.directory/"classifier.joblib").write_bytes(b"not a real artifact")

    def test_local_artifact_needs_explicit_development_switch(self):
        import os
        from unittest.mock import patch
        self.make_manifest()
        with patch.dict(os.environ,{"ASCENSION_DEVELOPMENT_MODEL":"0"}):
            self.assertEqual(self.module.load_classifier(),(None,None))

    def test_corrupted_artifact_fails_before_deserialization(self):
        import os
        from unittest.mock import patch
        self.make_manifest()
        with patch.dict(os.environ,{"ASCENSION_DEVELOPMENT_MODEL":"1"}):
            with self.assertRaisesRegex(RuntimeError,"checksum"):
                self.module.load_classifier()

    def test_failed_candidate_cannot_be_loaded(self):
        import os
        from unittest.mock import patch
        self.make_manifest(development_release_eligible=False)
        with patch.dict(os.environ,{"ASCENSION_DEVELOPMENT_MODEL":"1"}):
            with self.assertRaisesRegex(RuntimeError,"not passed"):
                self.module.load_classifier()

    def test_nan_threshold_is_rejected(self):
        import os
        from unittest.mock import patch
        self.make_manifest(threshold=float("nan"))
        with patch.dict(os.environ,{"ASCENSION_DEVELOPMENT_MODEL":"1"}):
            with self.assertRaisesRegex(RuntimeError,"threshold"):
                self.module.load_classifier()
