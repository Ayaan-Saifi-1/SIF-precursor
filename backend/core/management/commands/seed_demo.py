import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from core.models import Report
from core.serializers import IntakeSerializer
from core.services import run_analysis
from data.demo_seed import demo_reports
class Command(BaseCommand):
    help="Add 80 explicitly synthetic reports. Existing IDs are preserved."
    def add_arguments(self,parser):
        parser.add_argument("--rules-only",action="store_true",help="Seed without loading SafetyBERT; the UI reports this degraded mode.")
    def handle(self,*args,**options):
        rows=list(demo_reports())
        data_path=Path(__file__).resolve().parents[4]/"data"/"demo_reports.csv"
        data_path.parent.mkdir(exist_ok=True)
        with data_path.open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        for i,row in enumerate(rows):
            if Report.objects.filter(report_id=row["report_id"]).exists(): continue
            s=IntakeSerializer(data=row);s.is_valid(raise_exception=True);r=s.save()
            inference=None
            if options["rules_only"]:
                def inference(*args): raise RuntimeError("Seeded without model; explicitly degraded.")
            run_analysis(r,inference=inference)
            if i%10==0: self.stdout.write(f"Seeded {i+1}/{len(rows)} synthetic reports.")
        self.stdout.write(self.style.SUCCESS(f"Demo seed complete: {Report.objects.filter(is_synthetic=True).count()} synthetic reports."))
