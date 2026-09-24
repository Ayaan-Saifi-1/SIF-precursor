"""Evaluate reserved development cases through the full advisory pipeline.

Review-required is abstention, never counted as a correct negative clearance.
This command appends evidence of model integration; it does not tune the model.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
from ml.development_scenarios import scenarios
from ml.safety_analyzer import analyze
from ml.sif_classifier import load_classifier


def check(output):
    if output.exists():
        raise ValueError("Refusing to overwrite evaluation evidence")
    if os.environ.get("ASCENSION_DEVELOPMENT_MODEL") != "1":
        raise ValueError("Enable local development model explicitly for this check")
    _, manifest=load_classifier()
    if (not manifest or manifest["model_version"] != "development-sif-scenario-v2.1"
            or manifest.get("inference_strategy") != "max(full_report,sentence_chunks)"):
        raise ValueError("The new development model is not active")
    results=[]
    for case in scenarios():
        if case["split"] != "test":
            continue
        report=dict(report_id=case["record_id"], description=case["description"],
                    report_type="Near Miss", context={}, is_synthetic=True)
        result=analyze(report)
        if result["status"] != "COMPLETE" or result["model_version"] != manifest["model_version"]:
            raise ValueError("A reserved report did not reach the active classifier")
        if len(result["embedding"]) != 768:
            raise ValueError("SafetyBERT representation is missing")
        if result["sif_label"] == "NON_SIF_POTENTIAL":
            raise ValueError("Development model must not automatically clear reports")
        results.append(dict(record_id=case["record_id"], expected=int(case["label"]),
            classifier_probability=result["sif_probability"], disposition=result["sif_label"],
            decision_source=result["decision_source"], review_required=result["review_required"],
            tags=result["iogp_rules"], missing_information=result["missing_information"]))
    summary=dict(model_version=manifest["model_version"], records=len(results),
        positive_dispositions=dict(Counter(r["disposition"] for r in results if r["expected"]==1)),
        controlled_dispositions=dict(Counter(r["disposition"] for r in results if r["expected"]==0)),
        limitations="Synthetic integration exercise; rule tags are not an evaluated learned tag model. Review-required is abstention, not a correct negative.",
        cases=results)
    output.write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="cases"},indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output)
