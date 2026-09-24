"""Counts for dashboard charts; one latest assessment per report, never rates."""
from datetime import timedelta
from math import isfinite
from collections import Counter
from django.utils import timezone
from django.utils.dateparse import parse_datetime

RULES = ["Bypassing Safety Controls", "Confined Space", "Driving", "Energy Isolation",
         "Hot Work", "Line of Fire", "Safe Mechanical Lifting", "Work Authorisation",
         "Working at Height"]


def chart_data(rows, days, now=None):
    now = now or timezone.now()
    start = timezone.localdate(now - timedelta(days=days))
    end = timezone.localdate(now)
    dates = [(start + timedelta(days=i)).isoformat() for i in range((end-start).days + 1)]
    daily = {date: dict(date=date, total=0, sif=0, unresolved=0, non_sif=0) for date in dates}
    sites = sorted({row["site"] for row in rows})
    totals = {site: 0 for site in sites}
    counts = {site: [0]*len(RULES) for site in sites}
    sif_counts = {site: [0]*len(RULES) for site in sites}
    without_tags = 0
    for row in rows:
        site = row["site"]
        totals[site] += 1
        tags = set(row.get("iogp_rules", []))
        if not tags.intersection(RULES):
            without_tags += 1
        for index, tag in enumerate(RULES):
            if tag in tags:
                counts[site][index] += 1
                sif_counts[site][index] += int(row["sif_label"] == "SIF_POTENTIAL")
        timestamp = parse_datetime(row["event_timestamp"])
        if timestamp is None or timezone.is_naive(timestamp):
            raise ValueError("Chart events require an aware event timestamp")
        day = timezone.localdate(timestamp).isoformat()
        if day in daily:
            item = daily[day]
            item["total"] += 1
            key = {"SIF_POTENTIAL": "sif", "NON_SIF_POTENTIAL": "non_sif"}.get(row["sif_label"], "unresolved")
            item[key] += 1
    sites.sort(key=lambda site: (-totals[site], site))
    classification = dict(sif=0, non_sif=0, unresolved=0)
    landscape = []
    barrier_failures = Counter()
    for row in rows:
        key = {"SIF_POTENTIAL": "sif", "NON_SIF_POTENTIAL": "non_sif"}.get(row["sif_label"], "unresolved")
        classification[key] += 1
        for barrier in {(b.get("name") or "Not identified", b.get("state") or "UNKNOWN")
                        for b in row.get("barriers", [])
                        if b.get("state") in ("FAILED", "BYPASSED", "ABSENT", "DEGRADED")}:
            barrier_failures[barrier] += 1
        probability = row.get("sif_probability")
        if (isinstance(probability, bool) or not isinstance(probability, (int, float))
                or not isfinite(probability) or not 0 <= probability <= 1
                or row.get("model_applicable") is False):
            probability = None
        landscape.append(dict(report_id=row.get("report_id", ""), site=row["site"],
            activity=row.get("activity") or "Not identified",
            precursor=", ".join(row.get("hazards", [])) or "Not identified",
            priority=row.get("priority") or "UNKNOWN", probability=probability,
            model_version=row.get("model_version") or "Unavailable",
            is_synthetic=bool(row.get("is_synthetic"))))
    return dict(rules=RULES, sites=sites, counts=[counts[s] for s in sites],
        sif_counts=[sif_counts[s] for s in sites], site_totals=[totals[s] for s in sites],
        daily=list(daily.values()), total_reports=len(rows), untagged_reports=without_tags,
        synthetic_reports=sum(bool(r.get("is_synthetic")) for r in rows), timezone=str(timezone.get_current_timezone()),
        classification=classification, landscape=landscape,
        report_types=grouped_counts(rows, "report_type"), priorities=grouped_counts(rows, "priority", ["LOW","MEDIUM","HIGH","CRITICAL"]),
        barrier_failures=[dict(name=name,state=state,count=count) for (name,state),count in barrier_failures.most_common()],
        note="A report may have multiple rule tags. Counts are reported observations, not incident rates or validated risk estimates.")


def grouped_counts(rows, key, order=None):
    groups={}
    for row in rows:
        name=row.get(key) or "Not identified"
        item=groups.setdefault(name,dict(name=name,total=0,sif=0,non_sif=0,unresolved=0))
        item["total"]+=1
        label={"SIF_POTENTIAL":"sif","NON_SIF_POTENTIAL":"non_sif"}.get(row["sif_label"],"unresolved")
        item[label]+=1
    names=[name for name in (order or []) if name in groups]
    names+=sorted(set(groups)-set(names))
    return [groups[name] for name in names]
