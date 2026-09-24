from django.db import models

class Report(models.Model):
    report_id=models.CharField(max_length=80,unique=True)
    source_record_id=models.CharField(max_length=120)
    source_system=models.CharField(max_length=120,default="MANUAL_ENTRY")
    schema_version=models.CharField(max_length=40,default="canonical-1")
    source_hash=models.CharField(max_length=64)
    context=models.JSONField(default=dict)
    site=models.CharField(max_length=120)
    department=models.CharField(max_length=120)
    report_type=models.CharField(max_length=30)
    event_timestamp=models.DateTimeField(db_index=True)
    description=models.TextField()
    immediate_action=models.TextField(blank=True)
    is_synthetic=models.BooleanField(default=False)
    source_snapshot=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=["-created_at"]
        constraints=[models.UniqueConstraint(fields=["source_system","source_record_id"],name="unique_source_record")]

class Analysis(models.Model):
    report=models.ForeignKey(Report,on_delete=models.PROTECT,related_name="analyses")
    payload=models.JSONField()
    sif_label=models.CharField(max_length=30,db_index=True)
    priority=models.CharField(max_length=20,db_index=True)
    model_version=models.CharField(max_length=160)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=["-created_at","-id"]

class ReviewItem(models.Model):
    report=models.OneToOneField(Report,on_delete=models.PROTECT,related_name="review")
    analysis=models.ForeignKey(Analysis,on_delete=models.PROTECT)
    priority=models.CharField(max_length=20)
    review_reason=models.JSONField(default=list)
    status=models.CharField(max_length=40,default="OPEN")
    version=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)

class ReviewDecision(models.Model):
    review=models.ForeignKey(ReviewItem,on_delete=models.PROTECT,related_name="decisions")
    decision=models.CharField(max_length=40)
    reviewer=models.CharField(max_length=120)
    identity_verified=models.BooleanField(default=False)
    override_reason=models.TextField(blank=True)
    ai_recommendation=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=["-created_at"]

class AuditEvent(models.Model):
    report=models.ForeignKey(Report,on_delete=models.PROTECT)
    event_type=models.CharField(max_length=60)
    payload=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=["-created_at"]
