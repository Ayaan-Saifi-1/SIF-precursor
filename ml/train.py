"""Candidate training. Requires reviewed, non-synthetic labels and four splits."""
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import confusion_matrix,precision_score,recall_score,fbeta_score,average_precision_score,brier_score_loss
from xgboost import XGBClassifier
import joblib
from ml.encoder import encode,ROOT
from ml.extractor import extract
from ml.sif_classifier import features,FEATURE_VERSION

def metrics(y,p,threshold):
    pred=p>=threshold
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return dict(recall=float(recall_score(y,pred,zero_division=0)),precision=float(precision_score(y,pred,zero_division=0)),
        f2=float(fbeta_score(y,pred,beta=2,zero_division=0)),pr_auc=float(average_precision_score(y,p)),
        false_negative_rate=float(fn/(fn+tp)) if fn+tp else None,npv=float(tn/(tn+fn)) if tn+fn else None,
        brier=float(brier_score_loss(y,p)),confusion_matrix=[[int(tn),int(fp)],[int(fn),int(tp)]])

def validate_rows(rows):
    if not rows: raise ValueError("Dataset is empty.")
    groups={};texts=set()
    for r in rows:
        if r.get("is_synthetic","").lower()!="false": raise ValueError("Synthetic or unmarked data cannot enter this training/evaluation pipeline.")
        if r.get("hse_reviewed","").lower()!="true": raise ValueError("Each label needs HSE review.")
        if r.get("split") not in ["train","calibration","validation","test"]: raise ValueError("Assign all four independent splits.")
        if r.get("label") not in ["0","1"]: raise ValueError("Use expert-confirmed 0/1 labels; uncertain reports remain unlabelled.")
        group=r.get("event_group")
        if not group: raise ValueError("event_group is required to prevent event leakage.")
        if group in groups and groups[group]!=r["split"]: raise ValueError("An event group crosses dataset splits.")
        groups[group]=r["split"]
        normalized=" ".join(r["description"].lower().split())
        if normalized in texts: raise ValueError("Deduplicate narratives before training.")
        texts.add(normalized)
    for split in ["train","calibration","validation","test"]:
        subset=[r for r in rows if r["split"]==split]
        if {r["label"] for r in subset}!={"0","1"}: raise ValueError(f"{split} needs both classes.")
        if len(subset)<10: raise ValueError(f"{split} needs at least ten reviewed reports for an experiment; this is not a production adequacy criterion.")

def train(dataset,output,min_recall):
    raw=dataset.read_bytes()
    rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()));validate_rows(rows)
    buckets={}
    for split in ["train","calibration","validation","test"]:
        selected=[r for r in rows if r["split"]==split]
        x=np.asarray([np.concatenate([encode(r["description"]),features(extract(r["description"]),r.get("report_type","Near Miss"))]) for r in selected])
        y=np.asarray([int(r["label"]) for r in selected]);buckets[split]=(selected,x,y)
    tr,x,y=buckets["train"]
    estimator=XGBClassifier(n_estimators=150,max_depth=3,learning_rate=.05,subsample=.9,colsample_bytree=.9,eval_metric="logloss",random_state=42,n_jobs=4)
    estimator.fit(x,y)
    model=CalibratedClassifierCV(FrozenEstimator(estimator),method="sigmoid")
    model.fit(buckets["calibration"][1],buckets["calibration"][2])
    vy=buckets["validation"][2];vp=model.predict_proba(buckets["validation"][1])[:,1]
    candidates=[float(t) for t in np.unique(vp) if recall_score(vy,vp>=t)>=min_recall]
    threshold=max(candidates,key=lambda t:(fbeta_score(vy,vp>=t,beta=2),t))
    negatives=[float(t) for t in np.unique(vp) if t<threshold and np.sum(vp<=t)>=5 and np.mean(vy[vp<=t]==0)>=.99]
    negative_threshold=max(negatives) if negatives else None
    baseline=make_pipeline(TfidfVectorizer(ngram_range=(1,2),max_features=20000),LogisticRegression(class_weight="balanced",max_iter=1500,random_state=42))
    baseline.fit([r["description"] for r in tr],y)
    bp=baseline.predict_proba([r["description"] for r in buckets["validation"][0]])[:,1]
    bt=max([float(t) for t in np.unique(bp) if recall_score(vy,bp>=t)>=min_recall],key=lambda t:(fbeta_score(vy,bp>=t,beta=2),t))
    ty=buckets["test"][2];tp=model.predict_proba(buckets["test"][1])[:,1]
    manifest=dict(model_version="safetybert-xgboost-"+hashlib.sha256(raw).hexdigest()[:12],feature_version=FEATURE_VERSION,
        threshold=threshold,negative_threshold=negative_threshold,hse_validated=False,status="CANDIDATE_ONLY",
        dataset_sha256=hashlib.sha256(raw).hexdigest(),encoder=json.loads((ROOT/"ml"/"models"/"provenance.json").read_text()),
        calibration="sigmoid / held-out calibration set",sample_sizes={k:len(v[0]) for k,v in buckets.items()},
        validation=metrics(vy,vp,threshold),locked_test=metrics(ty,tp,threshold),
        benchmark=dict(name="TF-IDF + LogisticRegression",threshold=bt,locked_test=metrics(ty,baseline.predict_proba([r["description"] for r in buckets["test"][0]])[:,1],bt)),
        limitations=["Small-sample metrics are not production assurance.","Temporal and unseen-site holdouts and independent HSE sign-off remain required."])
    output.mkdir(parents=True,exist_ok=False)
    joblib.dump(model,output/"calibrated.joblib");joblib.dump(baseline,output/"baseline.joblib")
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("dataset",type=Path);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--minimum-recall",type=float,default=.95);a=p.parse_args()
    if not 0<a.minimum_recall<=1:p.error("Minimum recall must be in (0,1].")
    train(a.dataset,a.output,a.minimum_recall)
