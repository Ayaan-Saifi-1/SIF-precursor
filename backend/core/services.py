from django.db import transaction
from ml.safety_analyzer import analyze
from .models import Analysis,ReviewItem,AuditEvent
def report_data(report):
    return dict(report_id=report.report_id,site=report.site,department=report.department,report_type=report.report_type,
                event_timestamp=report.event_timestamp.isoformat(),description=report.description,
                immediate_action=report.immediate_action,is_synthetic=report.is_synthetic,context=report.context,
                source_record_id=report.source_record_id,source_system=report.source_system,schema_version=report.schema_version,
                source_hash=report.source_hash,ingested_at=report.created_at.isoformat())
def run_analysis(report,inference=None):
    payload=analyze(report_data(report),inference=inference)
    with transaction.atomic():
        analysis=Analysis.objects.create(report=report,payload=payload,sif_label=payload["sif_label"],
                                         priority=payload["priority"],model_version=payload["model_version"])
        if payload["review_required"]:
            item,created=ReviewItem.objects.get_or_create(report=report,defaults=dict(analysis=analysis,priority=payload["priority"],review_reason=payload["review_reasons"]))
            if not created:
                item.analysis=analysis; item.priority=payload["priority"]; item.review_reason=payload["review_reasons"]
                item.status="OPEN"; item.version+=1; item.save()
        AuditEvent.objects.create(report=report,event_type="ANALYSIS_CREATED",payload=dict(analysis_id=analysis.id,
            model_version=payload["model_version"],gate_version=payload["gate_version"],catalogue_version=payload["catalogue_version"],
            threshold=payload["threshold"],sif_label=payload["sif_label"],hard_gate=payload["hard_gate"]))
    return analysis
def public_analysis(analysis):
    p={k:v for k,v in analysis.payload.items() if k!="embedding"}
    p.update(analysis_id=analysis.id,analysis_timestamp=analysis.created_at.isoformat())
    return p
