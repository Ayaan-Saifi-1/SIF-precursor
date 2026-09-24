from datetime import datetime, timezone as utc
from django.test import SimpleTestCase
from core.dashboard_data import chart_data


class ChartAggregationTests(SimpleTestCase):
    def test_landscape_preserves_missing_probabilities_and_classification(self):
        base = dict(site="A", activity="Lifting", iogp_rules=[], hazards=["Suspended Load"],
                    event_timestamp="2026-09-20T08:00:00+05:30")
        cases = [dict(base, report_id="A", sif_label="SIF_POTENTIAL", sif_probability=None),
                 dict(base, report_id="B", sif_label="NON_SIF_POTENTIAL", sif_probability=0),
                 dict(base, report_id="C", sif_label="REVIEW_REQUIRED", sif_probability=.8),
                 dict(base, report_id="D", sif_label="REVIEW_REQUIRED", sif_probability=.9, model_applicable=False),
                 dict(base, report_id="E", sif_label="REVIEW_REQUIRED", sif_probability=float('nan'))]
        result = chart_data(cases, 7, datetime(2026,9,20,8,tzinfo=utc.utc))
        self.assertEqual(result["classification"], dict(sif=1, non_sif=1, unresolved=3))
        self.assertEqual([r["probability"] for r in result["landscape"]], [None, 0, .8, None, None])
        self.assertEqual(len(result["landscape"]), result["total_reports"])

    def test_tags_are_multilabel_but_never_duplicate_within_report(self):
        row=dict(site="Site A", iogp_rules=["Line of Fire", "Line of Fire", "Energy Isolation"],
                 sif_label="SIF_POTENTIAL", event_timestamp="2026-09-19T19:00:00+00:00", is_synthetic=True)
        result=chart_data([row],7,datetime(2026,9,20,8,tzinfo=utc.utc))
        self.assertEqual(sum(result["counts"][0]),2)
        self.assertEqual(sum(result["sif_counts"][0]),2)
        self.assertEqual(result["total_reports"],1)
        self.assertEqual(result["synthetic_reports"],1)
        self.assertEqual(next(d for d in result["daily"] if d["date"]=="2026-09-20")["total"],1)

    def test_unresolved_is_not_a_negative_and_untagged_is_counted(self):
        row=dict(site="Site B",iogp_rules=[],sif_label="REVIEW_REQUIRED",
                 event_timestamp="2026-09-20T08:00:00+05:30")
        result=chart_data([row],7,datetime(2026,9,20,8,tzinfo=utc.utc))
        self.assertEqual(result["untagged_reports"],1)
        self.assertEqual(sum(d["unresolved"] for d in result["daily"]),1)
        self.assertEqual(sum(d["non_sif"] for d in result["daily"]),0)
        self.assertEqual(sum(result["counts"][0]),0)

    def test_empty_period_has_zero_daily_buckets(self):
        result=chart_data([],7,datetime(2026,9,20,8,tzinfo=utc.utc))
        self.assertEqual(result["sites"],[])
        self.assertEqual(len(result["daily"]),8)
        self.assertTrue(all(d["total"]==0 for d in result["daily"]))

    def test_dashboard_groupings_keep_unresolved_separate(self):
        rows=[dict(site="A",activity="Maintenance",report_type="Near Miss",priority="HIGH",iogp_rules=[],barriers=[{"name":"Isolation","state":"FAILED"}],
                   sif_label="SIF_POTENTIAL",event_timestamp="2026-09-20T08:00:00+05:30"),
              dict(site="A",activity="Maintenance",report_type="Near Miss",priority="LOW",iogp_rules=[],barriers=[{"name":"Isolation","state":"FAILED"}],
                   sif_label="REVIEW_REQUIRED",event_timestamp="2026-09-20T08:00:00+05:30")]
        result=chart_data(rows,7,datetime(2026,9,20,8,tzinfo=utc.utc))
        self.assertEqual(result["report_types"][0],dict(name="Near Miss",total=2,sif=1,non_sif=0,unresolved=1))
        self.assertEqual(result["barrier_failures"][0],dict(name="Isolation",state="FAILED",count=2))
