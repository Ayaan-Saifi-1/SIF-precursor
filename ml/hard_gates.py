"""Non-compensatory gates. Probability and recurrence cannot cancel a gate."""
def evaluate(facts, probability=None, recurrence=0):
    states = [b["state"] for b in facts["barriers"] if b.get("critical",True)]
    reasons = []
    priority = "LOW"
    label = "REVIEW_REQUIRED"
    if facts["credible_fatal"] and any(s in ["FAILED","BYPASSED","ABSENT"] for s in states):
        reasons = ["Credible fatal consequence", "Critical barrier failed, bypassed or absent"]
        priority, label = "CRITICAL", "SIF_POTENTIAL"
    elif facts["severe_hazard"] and facts["direct_exposure"] and any(s in ["DEGRADED","FAILED","ABSENT","BYPASSED"] for s in states):
        reasons = ["High-energy hazard", "Direct exposure", "Critical control weakened"]
        priority, label = "HIGH", "SIF_POTENTIAL"
    elif facts["severe_hazard"] and (not states or any(s in ["UNKNOWN","UNVERIFIED"] for s in states)):
        reasons = ["Severe hazard", "Critical control unknown or unverified"]
        priority = "HIGH"
    elif facts["credible_fatal"]:
        priority, label = "HIGH", "SIF_POTENTIAL"
    elif facts["missing_information"]:
        priority = "MEDIUM"
    # Ranking can only raise priority. This score is not a calibrated probability.
    score = (probability or 0)*60 + min(max(recurrence,0),10)*2 + (20 if facts["direct_exposure"] else 0)
    floor = {"LOW":0,"MEDIUM":30,"HIGH":60,"CRITICAL":90}[priority]
    score = round(max(score, floor),1)
    if score >= 90: priority = "CRITICAL"
    elif score >= 60 and priority in ["LOW","MEDIUM"]: priority="HIGH"
    elif score >= 30 and priority=="LOW": priority="MEDIUM"
    return dict(priority=priority, risk_level=priority, sif_label=label, ranking_score=score,
                hard_gate=dict(triggered=bool(reasons),reason=reasons,mandatory_review=bool(reasons)))
