import json
from pathlib import Path
from django.core.management.base import BaseCommand
from core.models import Report
from ml.pattern_engine import semantic_clusters
class Command(BaseCommand):
    help="Compute actual SafetyBERT/HDBSCAN clusters separately from curated families."
    def handle(self,*args,**options):
        rows=[r.analyses.first().payload for r in Report.objects.all() if r.analyses.exists()]
        output=Path(__file__).resolve().parents[4]/"data"/"semantic_clusters.json"
        clusters=semantic_clusters(rows)
        output.write_text(json.dumps(clusters,indent=2),encoding="utf-8")
        self.stdout.write(f"Stored {len(clusters)} semantic clusters at {output}")
