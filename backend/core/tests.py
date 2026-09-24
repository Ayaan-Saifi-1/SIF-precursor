import copy,csv,io
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,SimpleTestCase,override_settings
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from ml.extractor import extract
from ml.hard_gates import evaluate
from ml.safety_analyzer import analyze
from ml.density import density
from data.demo_seed import SAMPLES
from core.models import Report,Analysis,ReviewItem,ReviewDecision,AuditEvent

def unavailable(*args): raise RuntimeError("Inference failed")
def input_data(report_id="TEST-001",case=0):
    return dict(report_id=report_id,site="Test site",department="Operations",report_type="Near Miss",
                event_timestamp=(timezone.now()-timedelta(hours=2)).isoformat(),description=SAMPLES[case]["description"],
                immediate_action="",is_synthetic=True)

class SafetyCases(SimpleTestCase):
    def test_suspended_load(self):
        r=analyze(input_data(),inference=unavailable)
        self.assertEqual(r["sif_label"],"SIF_POTENTIAL")
        self.assertTrue(r["hard_gate"]["triggered"])
        self.assertIn("Safe Mechanical Lifting",r["iogp_rules"])
        self.assertIn(r["barriers"][0]["state"],["DEGRADED","FAILED"])
    def test_psv_bypass(self):
        r=analyze(input_data(case=1),inference=unavailable)
        self.assertEqual(r["priority"],"CRITICAL")
        self.assertEqual(r["barriers"][0]["state"],"BYPASSED")
    def test_drill_is_not_high_risk(self):
        r=analyze(input_data(case=2),inference=unavailable)
        self.assertEqual(r["priority"],"LOW")
        self.assertEqual(r["exposures"],[])
        self.assertEqual(r["barriers"][0]["state"],"EFFECTIVE")
        self.assertNotEqual(r["sif_label"],"NON_SIF_POTENTIAL")
        self.assertEqual(r["status"],"ANALYSIS_UNAVAILABLE")
    def test_vague_requires_review(self):
        r=analyze(input_data(case=3),inference=unavailable)
        self.assertEqual(r["sif_label"],"REVIEW_REQUIRED")
        self.assertEqual(set(r["missing_information"]),{"hazard","exposure","barrier status","equipment condition"})
    def test_excavation(self):
        r=analyze(input_data(case=4),inference=unavailable)
        self.assertEqual(r["priority"],"HIGH")
        self.assertEqual(r["barriers"][0]["state"],"UNVERIFIED")
        self.assertIn("Work Authorisation",r["iogp_rules"])
    def test_evidence_offsets(self):
        for s in SAMPLES:
            f=extract(s["description"])
            for e in f["evidence_spans"]: self.assertEqual(s["description"][e["start_offset"]:e["end_offset"]],e["text"])
    def test_negated_bypass_not_bypassed(self):
        f=extract("During operation the PSV was not bypassed. No worker was exposed.")
        self.assertEqual(f["barriers"][0]["state"],"UNKNOWN")
    def test_presence_does_not_prove_effectiveness(self):
        f=extract("H2S monitoring. Gas detector installed.")
        self.assertNotEqual(f["barriers"][0]["state"],"EFFECTIVE")
    def test_barrier_state_scoping(self):
        f=extract("During operation the PSV was tested and found functional; gas detector failed during H2S monitoring.")
        states={b["name"]:b["state"] for b in f["barriers"]}
        self.assertEqual(states["Pressure Safety Valve"],"EFFECTIVE")
        self.assertEqual(states["Gas Detector"],"FAILED")
    def test_contradiction_keeps_failure(self):
        f=extract("During operation the PSV was tested and found functional. Later the PSV failed.")
        self.assertTrue(f["barriers"][0]["contradictory"])
        self.assertEqual(f["barriers"][0]["state"],"FAILED")
    def test_immediate_action_never_erases_original_failure(self):
        r=input_data(case=1);r["immediate_action"]="PSV tested and found functional after repair."
        self.assertEqual(analyze(r,inference=unavailable)["barriers"][0]["state"],"BYPASSED")
    def test_probability_monotonicity(self):
        levels={"LOW":0,"MEDIUM":1,"HIGH":2,"CRITICAL":3}
        for s in SAMPLES:
            f=extract(s["description"]);previous=-1
            for i in range(101):
                level=levels[evaluate(f,i/100)["priority"]]
                self.assertGreaterEqual(level,previous);previous=level
    def test_barrier_monotonicity(self):
        f=extract(SAMPLES[0]["description"])
        for p in [0,.1,.5,.99,1]:
            f["barriers"][0]["state"]="EFFECTIVE"; a=evaluate(f,p)["ranking_score"]
            f["barriers"][0]["state"]="FAILED"; b=evaluate(f,p)["ranking_score"]
            self.assertGreaterEqual(b,a)
    def test_gate_invariance(self):
        f=extract(SAMPLES[1]["description"])
        for recurrence in [0,1,100]:
            self.assertEqual(evaluate(f,0,recurrence)["priority"],"CRITICAL")
    def test_model_failure_no_silent_negative(self):
        r=analyze(input_data(case=3),inference=unavailable)
        self.assertIsNone(r["sif_probability"]);self.assertTrue(r["review_required"])
        self.assertEqual(r["status"],"ANALYSIS_UNAVAILABLE")
    def test_density_counts_and_prior(self):
        rows=[dict(site="Tiny",sif_label="SIF_POTENTIAL" if i<2 else "REVIEW_REQUIRED") for i in range(4)]
        r=density(rows)[0]
        self.assertEqual(r["raw_density"],50);self.assertEqual(r["adjusted_density"],50)
        self.assertEqual(r["review_count"],2);self.assertTrue(r["sample_size_warning"])
        self.assertLess(r["lower_bound"],50);self.assertGreater(r["upper_bound"],50)
    def test_empty_density(self):self.assertEqual(density([]),[])
    def test_zero_sif_density(self):
        r=density([dict(site="A",sif_label="REVIEW_REQUIRED")])[0]
        self.assertEqual(r["raw_density"],0);self.assertEqual(r["adjusted_density"],33.3)

class APICases(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.mock=patch("ml.sif_classifier.predict",side_effect=RuntimeError("Unavailable"))
        self.mock.start();self.addCleanup(self.mock.stop)
    def submit(self,data=None):
        response=self.client.post("/api/analyze/",data or input_data(),format="json")
        self.assertEqual(response.status_code,201,response.data);return response
    def test_end_to_end_review(self):
        r=self.submit()
        self.assertEqual(Report.objects.count(),1);self.assertEqual(Analysis.objects.count(),1)
        item=ReviewItem.objects.get()
        d=self.client.post(f"/api/reviews/{item.id}/decision/",dict(decision="CONFIRM",reviewer="Demo reviewer",version=item.version),format="json")
        self.assertEqual(d.status_code,200);self.assertEqual(ReviewDecision.objects.count(),1)
        self.assertEqual(Analysis.objects.get().payload["sif_label"],r.data["sif_label"])
        self.assertEqual(AuditEvent.objects.filter(event_type="HSE_DECISION").count(),1)
    def test_override_reason_required(self):
        self.submit();item=ReviewItem.objects.get()
        d=self.client.post(f"/api/reviews/{item.id}/decision/",dict(decision="DISAGREE",reviewer="Reviewer",version=1),format="json")
        self.assertEqual(d.status_code,400);self.assertEqual(ReviewDecision.objects.count(),0)
    def test_stale_review_rejected(self):
        self.submit();item=ReviewItem.objects.get()
        payload=dict(decision="ESCALATE",reviewer="Reviewer",version=1)
        self.assertEqual(self.client.post(f"/api/reviews/{item.id}/decision/",payload,format="json").status_code,200)
        self.assertEqual(self.client.post(f"/api/reviews/{item.id}/decision/",payload,format="json").status_code,409)
        self.assertEqual(ReviewDecision.objects.count(),1)
    def test_reanalysis_is_append_only(self):
        self.submit()
        self.client.post("/api/analyze/",{"report_id":"TEST-001"},format="json")
        self.assertEqual(Analysis.objects.count(),2);self.assertEqual(ReviewItem.objects.count(),1)
    def test_duplicate_id(self):
        self.submit()
        self.assertEqual(self.client.post("/api/analyze/",input_data(),format="json").status_code,400)
        self.assertEqual(Report.objects.count(),1)
    def test_duplicate_source(self):
        row=input_data();row.update(source_system="SRC",source_record_id="1");self.submit(row)
        row["report_id"]="TEST-002"
        self.assertEqual(self.client.post("/api/analyze/",row,format="json").status_code,400)
    def test_unknown_source_fields_preserved(self):
        row=input_data();row["custom_source_field"]="Original value"
        row["context"]={"task_training":"Expired","pressure":"42 bar"}
        self.submit(row);report=Report.objects.get()
        self.assertEqual(report.source_snapshot["custom_source_field"],"Original value")
        self.assertEqual(len(report.source_hash),64)
        self.assertEqual(report.context["pressure"],"42 bar")
    def test_future_timestamp(self):
        row=input_data();row["event_timestamp"]=(timezone.now()+timedelta(days=1)).isoformat()
        self.assertEqual(self.client.post("/api/analyze/",row,format="json").status_code,400)
    def test_missing_required_field(self):
        row=input_data();del row["site"]
        self.assertEqual(self.client.post("/api/analyze/",row,format="json").status_code,400)
    def test_import_atomic_validation(self):
        rows=[input_data("GOOD"),input_data("BAD")];rows[1]["report_type"]="Invalid"
        stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
        file=SimpleUploadedFile("reports.csv",stream.getvalue().encode(),content_type="text/csv")
        r=self.client.post("/api/reports/import/",{"file":file},format="multipart")
        self.assertEqual(r.status_code,400);self.assertEqual(Report.objects.count(),0)
    def test_import_csv(self):
        row=input_data();stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=row.keys());w.writeheader();w.writerow(row)
        r=self.client.post("/api/reports/import/",{"file":SimpleUploadedFile("reports.csv",stream.getvalue().encode())},format="multipart")
        self.assertEqual(r.status_code,201,r.data);self.assertEqual(r.data["imported"],1)
    def test_xlsx_import(self):
        from openpyxl import Workbook
        row=input_data();wb=Workbook();ws=wb.active;ws.append(list(row));ws.append(list(row.values()))
        stream=io.BytesIO();wb.save(stream)
        r=self.client.post("/api/reports/import/",{"file":SimpleUploadedFile("reports.xlsx",stream.getvalue())},format="multipart")
        self.assertEqual(r.status_code,201,r.data)
    def test_failure_stays_visible(self):
        r=self.submit();self.assertEqual(r.data["status"],"ANALYSIS_UNAVAILABLE")
        self.assertEqual(len(self.client.get("/api/reports/").data),1)
        self.assertEqual(len(self.client.get("/api/reviews/").data),1)
    def test_density_window_validation(self):
        self.assertEqual(self.client.get("/api/dashboard/site-density/?days=no").status_code,400)
    def test_all_read_routes(self):
        self.submit()
        for path in ["health","samples","reports","dashboard/summary","dashboard/site-density","dashboard/activity-density","patterns","reviews"]:
            self.assertEqual(self.client.get(f"/api/{path}/").status_code,200,path)
    @override_settings(DEMO_MODE=False)
    def test_anonymous_denied_outside_demo(self):
        self.assertIn(self.client.get("/api/reports/").status_code,[401,403])
    def test_remote_anonymous_denied(self):
        self.assertIn(self.client.get("/api/reports/",REMOTE_ADDR="192.0.2.1").status_code,[401,403])

    def test_cross_origin_demo_write_denied(self):
        r=self.client.post("/api/analyze/",input_data(),format="json",HTTP_ORIGIN="https://untrusted.example")
        self.assertEqual(r.status_code,403)

class AdditionalSafetyCases(SimpleTestCase):
    def test_two_barriers_in_one_sentence(self):
        f=extract("During operation the PSV was tested and found functional and the gas detector failed during H2S monitoring.")
        b={b["name"]:b for b in f["barriers"]}
        self.assertEqual(b["Pressure Safety Valve"]["state"],"EFFECTIVE")
        self.assertEqual(b["Gas Detector"]["state"],"FAILED")
    def test_drill_rule_tags_are_not_keyword_only(self):
        self.assertEqual(extract(SAMPLES[2]["description"])["iogp_rules"],[])
    def test_installed_control_presence_is_recorded(self):
        b=extract("H2S monitoring. Gas detector installed.")["barriers"][0]
        self.assertEqual(b["verification_status"],"PRESENT")
        self.assertEqual(b["state"],"UNKNOWN")
    def test_unvalidated_negative_threshold_abstains(self):
        def model(*args):
            return dict(probability=.1,encoder_status="READY",classifier_status="READY",model_version="test",
                        vector=[],threshold=.8,negative_threshold=None)
        r=analyze(input_data(case=2),inference=model)
        self.assertEqual(r["sif_label"],"REVIEW_REQUIRED")
    def test_validated_negative_threshold(self):
        def model(*args):
            return dict(probability=.1,encoder_status="READY",classifier_status="READY",model_version="test",
                        vector=[],threshold=.8,negative_threshold=.2)
        self.assertEqual(analyze(input_data(case=2),inference=model)["sif_label"],"NON_SIF_POTENTIAL")
    def test_training_rejects_synthetic(self):
        from ml.train import validate_rows
        with self.assertRaisesRegex(ValueError,"Synthetic"):
            validate_rows([dict(is_synthetic="true")])
    def test_training_group_leakage_rejected(self):
        from ml.train import validate_rows
        rows=[dict(description="Report "+str(i),is_synthetic="false",hse_reviewed="true",label=str(i%2),split=split,event_group="same") for i,split in enumerate(["train","test"])]
        with self.assertRaisesRegex(ValueError,"crosses"):
            validate_rows(rows)

class ConnectionAndAliasCases(TestCase):
    def test_cors_credentials(self):
        client=APIClient()
        response=client.options("/api/health/",HTTP_ORIGIN="http://localhost:3000",HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type")
        self.assertEqual(response["Access-Control-Allow-Origin"],"http://localhost:3000")
        self.assertEqual(response["Access-Control-Allow-Credentials"],"true")
    def test_entry_permit_alias(self):
        f=extract("Worker entered a tank for confined space work. Entry permit was absent. Oxygen deficiency was reported.")
        self.assertEqual(f["barriers"][0]["state"],"ABSENT")
        self.assertEqual(evaluate(f)["priority"],"CRITICAL")
    def test_untrusted_origin_not_allowed_by_cors(self):
        response=APIClient().options("/api/health/",HTTP_ORIGIN="https://untrusted.example",HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        self.assertNotIn("Access-Control-Allow-Origin",response)


class LanguageRegressionCases(SimpleTestCase):
    """New wording and counterexamples, independent of the five demo templates."""
    fresh_report = (
        "During removal of a pump, a rigger walked under the 2-tonne unit while it hung "
        "from a mobile crane. The lifting area had not been cordoned off. Nobody was hurt."
    )

    def result(self, text):
        return evaluate(extract(text))

    def test_fresh_lifting_report_has_a_fatal_pathway(self):
        facts = extract(self.fresh_report)
        self.assertEqual(facts["activity"], "Mechanical Lifting")
        self.assertIn("Suspended Load", facts["hazards"])
        self.assertTrue(facts["direct_exposure"])
        self.assertEqual(facts["barriers"][0]["state"], "ABSENT")
        self.assertEqual(self.result(self.fresh_report)["priority"], "CRITICAL")
        self.assertEqual(self.result(self.fresh_report)["sif_label"], "SIF_POTENTIAL")
        self.assertTrue(any(m["value"] == 2 and m["unit"] == "tonne" for m in facts["measurements"]))

    def test_unseen_lifting_paraphrases(self):
        cases = [
            "A mechanic was beneath a pump being hoisted by a crane. The exclusion barricade had been removed. There were no injuries.",
            "A fitter stood directly below the load hanging from an overhead hoist. The restricted area was not barricaded.",
            "A helper walked under a pipe held aloft by a crane. No cordon was provided.",
        ]
        for text in cases:
            with self.subTest(text=text):
                facts = extract(text)
                self.assertTrue(facts["direct_exposure"])
                self.assertEqual(facts["barriers"][0]["state"], "ABSENT")
                self.assertEqual(evaluate(facts)["sif_label"], "SIF_POTENTIAL")

    def test_negated_worker_exposure_is_not_a_failure_inference(self):
        text = "During crane lifting activity no worker was standing beneath the suspended load. The exclusion zone was tested and found functional."
        facts = extract(text)
        self.assertFalse(facts["direct_exposure"])
        self.assertEqual(facts["exposure_status"], "EXPLICITLY_NEGATED")
        self.assertEqual(facts["barriers"][0]["state"], "EFFECTIVE")
        self.assertFalse(evaluate(facts)["hard_gate"]["triggered"])

    def test_negated_bypass_with_unambiguous_following_valve_test(self):
        text = "During operation the PSV had not been bypassed. The valve was tested and found functional."
        facts = extract(text)
        self.assertEqual(facts["barriers"][0]["state"], "EFFECTIVE")
        self.assertFalse(evaluate(facts)["hard_gate"]["triggered"])

    def test_following_unrelated_failure_does_not_transfer(self):
        text = "During operation the PSV was tested and found functional. The motor failed during maintenance."
        facts = extract(text)
        psv = next(b for b in facts["barriers"] if b["name"] == "Pressure Safety Valve")
        self.assertEqual(psv["state"], "EFFECTIVE")

    def test_ambiguous_reference_does_not_assert_a_barrier_state(self):
        text = "During operation the PSV and gas detector were installed for H2S monitoring. It failed."
        facts = extract(text)
        self.assertTrue(all(b["state"] == "UNKNOWN" for b in facts["barriers"]))

    def test_negated_missing_cordon_is_not_absent(self):
        text = "A crane was lifting a suspended load. The exclusion barricade was not removed."
        facts = extract(text)
        self.assertNotEqual(facts["barriers"][0]["state"], "ABSENT")

    def test_classroom_hypothetical_is_not_an_actual_failed_detector(self):
        text = "The training briefing discussed H2S exposure and what to do if a gas detector failed. This was a classroom exercise."
        facts = extract(text)
        self.assertTrue(facts["context_only"])
        self.assertFalse(facts["credible_fatal"])
        self.assertEqual(evaluate(facts)["priority"], "LOW")
        self.assertTrue(any(m["assertion"] == "HYPOTHETICAL" for m in facts["contextual_mentions"]))

    def test_real_release_during_training_is_not_suppressed(self):
        text = "During a training exercise a real H2S release occurred. The gas detector failed and a worker exposed to H2S required assistance."
        facts = extract(text)
        self.assertFalse(facts["simulated"])
        self.assertEqual(evaluate(facts)["priority"], "CRITICAL")

    def test_conditional_barrier_failure_is_not_asserted(self):
        text = "H2S monitoring continued. If the gas detector failed the team would leave."
        facts = extract(text)
        self.assertNotEqual(facts["barriers"][0]["state"], "FAILED")
        self.assertNotEqual(evaluate(facts)["sif_label"], "SIF_POTENTIAL")

    def test_driving_alone_does_not_establish_a_collision_hazard(self):
        facts = extract("A truck was driving within the speed limit. No pedestrians were present. The spotter was in place.")
        self.assertEqual(facts["activity"], "Driving")
        self.assertEqual(facts["hazards"], [])
        self.assertFalse(evaluate(facts)["hard_gate"]["triggered"])

    def test_dangerous_driving_still_triggers(self):
        facts = extract("Driving a truck, driver speeding with a pedestrian behind. Pedestrian barrier was missing.")
        self.assertEqual(evaluate(facts)["priority"], "CRITICAL")

    def test_decimal_does_not_break_barrier_sentence(self):
        facts = extract("A crane was lifting a suspended load. The exclusion zone at 2.5 m was missing.")
        self.assertEqual(facts["barriers"][0]["state"], "ABSENT")

    def test_selected_state_quote_supports_selected_state(self):
        facts = extract("During operation the PSV was tested and found functional. Later the PSV failed.")
        self.assertIn("failed", facts["barriers"][0]["evidence"])
        self.assertTrue(facts["barriers"][0]["contradictory"])

    def test_all_new_evidence_offsets_are_exact(self):
        for text in [self.fresh_report, "The training briefing discussed H2S and what to do if a gas detector failed."]:
            facts = extract(text)
            for span in facts["evidence_spans"] + facts["contextual_mentions"]:
                self.assertEqual(text[span["start_offset"]:span["end_offset"]], span["text"])

    def test_encoder_without_classifier_is_still_not_a_probability(self):
        def encoder_only(*args):
            return dict(probability=None, encoder_status="READY", classifier_status="NOT_TRAINED",
                        model_version="SafetyBERT / classifier pending", vector=[], threshold=None)
        report = input_data()
        report["description"] = self.fresh_report
        result = analyze(report, inference=encoder_only)
        self.assertEqual(result["sif_label"], "SIF_POTENTIAL")
        self.assertEqual(result["decision_source"], "SAFETY_RULES")
        self.assertIsNone(result["sif_probability"])
        self.assertEqual(result["status"], "ANALYSIS_UNAVAILABLE")
