from collections import defaultdict
from scipy.stats import beta

def density(rows,key="site"):
    groups=defaultdict(list)
    for row in rows: groups[row.get(key) or "Not identified"].append(row)
    result=[]
    for name,items in groups.items():
        # Eligible = structurally valid ingested reports; unresolved reports remain
        # in denominator, with a separate unresolved count and explicit warning.
        n=len(items); k=sum(r["sif_label"]=="SIF_POTENTIAL" for r in items)
        unknown=sum(r["sif_label"]=="REVIEW_REQUIRED" for r in items)
        a,b=k+1,n-k+1
        result.append(dict(name=name,sif_count=k,total_count=n,sample_size=n,
            raw_density=round(100*k/n,1),adjusted_density=round(100*a/(a+b),1),
            lower_bound=round(float(beta.ppf(.025,a,b))*100,1),
            upper_bound=round(float(beta.ppf(.975,a,b))*100,1),
            review_count=unknown,reliability_level="LOW" if n<30 else "MODERATE" if n<100 else "HIGH",
            sample_size_warning=n<30,prior="Beta(1,1)",eligible_definition="All structurally valid reports; review cases included"))
    return sorted(result,key=lambda x:(-x["adjusted_density"],-x["sample_size"],x["name"]))
