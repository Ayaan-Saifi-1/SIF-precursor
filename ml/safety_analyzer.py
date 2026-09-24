import logging
from ml.catalogue import VERSION
from ml.extractor import extract
from ml.hard_gates import evaluate

logger = logging.getLogger(__name__)
def analyze(report, inference=None):
    facts=extract(report["description"])
    from ml.context import supplement
    facts=supplement(facts,report.get("context",{}))
    if inference is None:
        from ml.sif_classifier import predict
        inference=predict
    model=dict(probability=None,encoder_status="UNAVAILABLE",classifier_status="UNAVAILABLE",
               model_version="rules-only / model unavailable",vector=[],threshold=None)
    error=None
    try:
        model=inference(report["description"],facts,report["report_type"])
    except Exception as exc:
        error="SafetyBERT inference unavailable; report requires human review."
        logger.warning("Analysis model unavailable: %s",type(exc).__name__)
    result=evaluate(facts,model["probability"])
    unavailable=model["classifier_status"]!="READY"
    if not unavailable and not facts["missing_information"] and result["sif_label"] != "SIF_POTENTIAL":
        if model["probability"]>=model["threshold"]:
            result["sif_label"]="SIF_POTENTIAL"
        elif model.get("negative_threshold") is not None and model["probability"]<=model["negative_threshold"]:
            result["sif_label"]="NON_SIF_POTENTIAL"
        else:
            result["sif_label"]="REVIEW_REQUIRED"
            facts["missing_information"].append("model probability lies in the review band")
    if result["sif_label"]=="SIF_POTENTIAL" and result["priority"] in ["LOW","MEDIUM"]:
        result["priority"]=result["risk_level"]="HIGH"
    reasons=list(result["hard_gate"]["reason"]) + list(facts["missing_information"])
    if unavailable:
        reasons.append(error or "SIF classifier needs HSE-labelled training and validation data")
    return dict(**report,**facts,**result,sif_probability=model["probability"],
                status="ANALYSIS_UNAVAILABLE" if unavailable else "COMPLETE",
                encoder_status=model["encoder_status"],classifier_status=model["classifier_status"],
                model_version=model["model_version"],embedding=model["vector"],
                decision_source="SAFETY_RULES" if result["hard_gate"]["triggered"] or facts["credible_fatal"] else "ABSTENTION" if unavailable else "MODEL",
                review_required=unavailable or bool(reasons) or result["sif_label"]=="SIF_POTENTIAL",
                review_reasons=list(dict.fromkeys(reasons)),model_error=error,
                catalogue_version=VERSION,gate_version="gates-1",threshold=model["threshold"],
                calibration_version="unavailable" if unavailable else model["model_version"],
                pattern_id=None,similar_report_count=0)
