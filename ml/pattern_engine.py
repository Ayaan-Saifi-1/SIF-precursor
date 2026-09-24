from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
import numpy as np
from ml.catalogue import FAMILIES

def discover(rows, now=None):
    now=now or datetime.now(timezone.utc)
    result=[]
    # Curated families are transparent deterministic groups. Semantic clusters
    # supplement them; neither is presented as the other.
    for f in FAMILIES:
        members=[r for r in rows if f["id"] in r.get("family_ids",[]) and not r.get("simulated")]
        if not members: continue
        def dt(r):
            d=datetime.fromisoformat(r["event_timestamp"].replace("Z","+00:00"))
            return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
        counts=[]
        for week in range(7,-1,-1):
            end=now-timedelta(days=week*7); start=end-timedelta(days=7)
            counts.append(sum(start<=dt(r)<end for r in members))
        ewma=[]; value=0.0
        for c in counts:
            value=.3*c+.7*value; ewma.append(round(value,2))
        before,after=sum(counts[:4]),sum(counts[4:])
        trend="INCREASING" if after>before*1.25 and after>=3 else "DECREASING" if before>after*1.25 else "STABLE"
        states=Counter(b["state"] for r in members for b in r["barriers"] if b["name"]==f["barrier"])
        result.append(dict(pattern_id=f["id"],title=f["hazard"]+" · "+f["barrier"],source="CURATED_FAMILY",
             report_count=len(members),sif_count=sum(r["sif_label"]=="SIF_POTENTIAL" for r in members),
             sites=sorted(set(r["site"] for r in members)),activities=[f["activity"]],dominant_hazard=f["hazard"],
             dominant_barrier=f["barrier"],dominant_barrier_state=states.most_common(1)[0][0] if states else "UNKNOWN",
             iogp_rules=f["rules"],trend=trend,severity="CRITICAL" if any(r["priority"]=="CRITICAL" for r in members) else "HIGH",
             weekly_counts=counts,ewma=ewma,report_ids=[r["report_id"] for r in members],
             period="Previous 8 weeks; four-week count comparison",pattern_version="curated-1 / ewma-alpha-0.3"))
    return sorted(result,key=lambda p:(p["trend"]!="INCREASING",-p["report_count"]))

def semantic_clusters(rows):
    import hdbscan
    eligible=[r for r in rows if r.get("embedding")]
    if len(eligible)<5: return []
    matrix=np.asarray([r["embedding"] for r in eligible],dtype=np.float64)
    labels=hdbscan.HDBSCAN(min_cluster_size=3,min_samples=2,metric="euclidean").fit_predict(matrix)
    clusters=defaultdict(list)
    for label,row in zip(labels,eligible):
        if label>=0: clusters[int(label)].append(row["report_id"])
    return [dict(cluster_id=f"SEM-{i+1:03}",report_ids=ids,report_count=len(ids),source="SafetyBERT + HDBSCAN")
            for i,ids in sorted(clusters.items())]
