import json
from functools import lru_cache
import numpy as np
from ml.encoder import encode, ROOT
FEATURE_VERSION="safety-features-2"
ARTIFACT_DIR=ROOT/"ml"/"models"/"sif"
def features(facts,report_type="Near Miss"):
    states=[b["state"] for b in facts["barriers"]]
    return np.asarray([float(facts[k]) for k in ["credible_fatal","direct_exposure","severe_hazard","simulated"]] +
        [float(s in states) for s in ["EFFECTIVE","DEGRADED","FAILED","BYPASSED","ABSENT","UNVERIFIED","UNKNOWN"]] +
        [float(bool(facts["missing_information"]))] +
        [float(report_type==r) for r in ["Unsafe Act","Unsafe Condition","Near Miss","Incident"]],dtype=np.float32)

@lru_cache(maxsize=1)
def load_classifier():
    import joblib
    if not (ARTIFACT_DIR/"manifest.json").exists():return None,None
    manifest=json.loads((ARTIFACT_DIR/"manifest.json").read_text())
    if manifest["feature_version"]!=FEATURE_VERSION or not manifest.get("hse_validated"):return None,None
    current=json.loads((ROOT/"ml"/"models"/"provenance.json").read_text())
    if manifest.get("encoder")!=current:raise RuntimeError("Classifier/encoder provenance mismatch.")
    threshold=manifest["threshold"];negative=manifest.get("negative_threshold")
    if not 0<=threshold<=1 or (negative is not None and not 0<=negative<threshold):
        raise RuntimeError("Invalid decision thresholds.")
    return joblib.load(ARTIFACT_DIR/"calibrated.joblib"),manifest

def predict(description,facts,report_type):
    vector=encode(description)
    classifier,manifest=load_classifier()
    if classifier is None:
        return dict(probability=None,encoder_status="READY",classifier_status="NOT_TRAINED",
                    model_version="SafetyBERT / classifier pending",vector=vector.tolist(),threshold=None,negative_threshold=None)
    p=float(classifier.predict_proba(np.concatenate([vector,features(facts,report_type)])[None,:])[0,1])
    if not np.isfinite(p) or not 0<=p<=1:raise ValueError("Invalid classifier probability")
    return dict(probability=p,encoder_status="READY",classifier_status="READY",model_version=manifest["model_version"],
                vector=vector.tolist(),threshold=manifest["threshold"],negative_threshold=manifest.get("negative_threshold"))
