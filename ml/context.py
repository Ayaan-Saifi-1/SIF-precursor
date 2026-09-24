"""Recorded context supplements evidence without downgrading narrative hazards."""
from ml.catalogue import FAMILIES
def supplement(facts,context):
    facts["structured_evidence"]=[dict(field=k,value=v,source_status="REPORTED") for k,v in context.items() if v not in ["",None,"UNKNOWN"]]
    for key,target in [("reported_hazard","hazards"),("reported_exposure","exposures")]:
        value=context.get(key)
        if value and value.upper() not in ["UNKNOWN","NONE","NO","NOT KNOWN"]:
            if value not in facts[target]: facts[target].append(value)
    if context.get("equipment_refs"):
        facts["equipment"].append(context["equipment_refs"])
    if context.get("reported_activity") and facts["activity"]=="Not identified":
        facts["activity"]=context["reported_activity"]
    barrier_name=context.get("barrier_name","")
    state=context.get("barrier_state","UNKNOWN")
    catalogue=next((f for f in FAMILIES if barrier_name.lower()==f["barrier"].lower()),None)
    if barrier_name:
        existing=next((b for b in facts["barriers"] if b["name"].lower()==barrier_name.lower()),None)
        if existing and state not in ["UNKNOWN","UNVERIFIED"] and existing["state"] not in ["UNKNOWN","UNVERIFIED",state]:
            existing["contradictory"]=True
            facts["missing_information"].append("contradictory structured barrier evidence")
        order=["EFFECTIVE","UNKNOWN","UNVERIFIED","DEGRADED","ABSENT","FAILED","BYPASSED"]
        if not existing or order.index(state)>order.index(existing["state"]):
            barrier=dict(name=barrier_name,state=state,critical=True,threat=catalogue["threat"] if catalogue else context.get("reported_threat","UNKNOWN"),
                verification_status=context.get("verification_status","UNKNOWN"),
                validation_status=context.get("validation_status","UNKNOWN"),
                evidence=context.get("barrier_evidence",""),confidence=0.0,match_method="structured_report",
                inferred=False,contradictory=bool(existing and existing.get("contradictory")))
            if existing: facts["barriers"].remove(existing)
            facts["barriers"].append(barrier)
        if catalogue:
            if catalogue["hazard"] not in facts["hazards"]: facts["hazards"].append(catalogue["hazard"])
            facts["severe_hazard"]=True
            facts["family_ids"]=list(dict.fromkeys(facts["family_ids"]+[catalogue["id"]]))
            facts["iogp_rules"]=list(dict.fromkeys(facts["iogp_rules"]+catalogue["rules"]))
            if state in ["FAILED","BYPASSED","ABSENT"]:
                facts["credible_fatal"]=True
                facts["potential_consequences"].append(catalogue["consequence"])
        elif state in ["FAILED","BYPASSED","ABSENT"]:
            facts["missing_information"].append("criticality and consequence of reported barrier need HSE assessment")
    if facts["equipment"]: facts["missing_information"]=[x for x in facts["missing_information"] if x!="equipment condition"]
    if facts["hazards"]: facts["missing_information"]=[x for x in facts["missing_information"] if x!="hazard"]
    if facts["exposures"]: facts["missing_information"]=[x for x in facts["missing_information"] if x!="exposure"]
    facts["sufficiency_status"]="REVIEW_REQUIRED" if facts["missing_information"] else "SUFFICIENT"
    return facts
