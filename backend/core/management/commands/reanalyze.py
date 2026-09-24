from django.core.management.base import BaseCommand
from core.models import Report
from core.services import run_analysis
class Command(BaseCommand):
    help="Append new analyses after a model is installed; previous assessments remain."
    def handle(self,*args,**options):
        for i,r in enumerate(Report.objects.all()):
            a=run_analysis(r)
            if i%10==0: self.stdout.write(f"Analysed {i+1}; encoder={a.payload['encoder_status']}")
