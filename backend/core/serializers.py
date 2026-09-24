import re,json,hashlib
from datetime import datetime
from django.utils import timezone
from rest_framework import serializers
from .models import Report

TYPES=["Unsafe Act","Unsafe Condition","Near Miss","Incident"]
class IntakeSerializer(serializers.Serializer):
    report_id=serializers.RegexField(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
    source_record_id=serializers.CharField(max_length=120,required=False,allow_blank=True)
    source_system=serializers.CharField(max_length=120,default="MANUAL_ENTRY")
    schema_version=serializers.CharField(max_length=40,default="canonical-1")
    context=serializers.JSONField(required=False,default=dict)
    site=serializers.CharField(max_length=120)
    department=serializers.CharField(max_length=120)
    report_type=serializers.ChoiceField(choices=TYPES)
    event_date=serializers.DateField(required=False,write_only=True)
    event_time=serializers.TimeField(required=False,write_only=True)
    event_timestamp=serializers.DateTimeField(required=False)
    description=serializers.CharField(min_length=8,max_length=12000)
    immediate_action=serializers.CharField(required=False,allow_blank=True,max_length=4000,default="")
    is_synthetic=serializers.BooleanField(default=False)
    def validate_report_id(self,value):
        if Report.objects.filter(report_id=value).exists():
            raise serializers.ValidationError("This report ID already exists.")
        return value
    def validate_context(self,value):
        if isinstance(value,str):
            try: value=json.loads(value)
            except ValueError: raise serializers.ValidationError("Context must be a JSON object.")
        if not isinstance(value,dict) or len(value)>80 or any(not isinstance(v,(str,int,float,bool,type(None))) for v in value.values()):
            raise serializers.ValidationError("Context must be a flat object of at most 80 fields.")
        if len(json.dumps(value))>16000: raise serializers.ValidationError("Context exceeds 16,000 characters.")
        states=["UNKNOWN","UNVERIFIED","EFFECTIVE","DEGRADED","FAILED","BYPASSED","ABSENT"]
        if value.get("barrier_state") and value["barrier_state"] not in states:
            raise serializers.ValidationError("Unknown barrier state.")
        return value
    def validate(self,data):
        data["source_record_id"]=data.get("source_record_id") or data["report_id"]
        if Report.objects.filter(source_system=data["source_system"],source_record_id=data["source_record_id"]).exists():
            raise serializers.ValidationError({"source_record_id":"This source record already exists."})
        if "event_timestamp" not in data:
            if "event_date" not in data or "event_time" not in data:
                raise serializers.ValidationError({"event_timestamp":"Provide a timestamp or both event date and time (IST)."})
            data["event_timestamp"]=timezone.make_aware(datetime.combine(data["event_date"],data["event_time"]))
        data.pop("event_date",None); data.pop("event_time",None)
        if data["event_timestamp"]>timezone.now():
            raise serializers.ValidationError({"event_timestamp":"Event time cannot be in the future."})
        return data
    def create(self,validated_data):
        snapshot=json.loads(json.dumps(dict(self.initial_data),default=str))
        digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()
        return Report.objects.create(**validated_data,source_snapshot=snapshot,source_hash=digest)

class DecisionSerializer(serializers.Serializer):
    decision=serializers.ChoiceField(choices=["CONFIRM","DISAGREE","REQUEST_MORE_INFORMATION","ESCALATE"])
    reviewer=serializers.CharField(max_length=120)
    override_reason=serializers.CharField(max_length=4000,required=False,allow_blank=True,default="")
    version=serializers.IntegerField(min_value=1)
    def validate(self,data):
        if data["decision"]=="DISAGREE" and not data["override_reason"].strip():
            raise serializers.ValidationError({"override_reason":"An override reason is required when disagreeing."})
        return data
