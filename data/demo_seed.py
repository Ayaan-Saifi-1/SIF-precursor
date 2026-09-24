"""Entirely synthetic; no OIL records or real operational statistics."""
from datetime import datetime,timedelta,timezone
SAMPLES=[
 dict(name="Suspended Load",description="Worker was observed standing beneath a suspended pipe while crane lifting activity was underway. No injury occurred.",report_type="Near Miss"),
 dict(name="PSV Bypass",description="During operation the pressure safety valve was found gagged/bypassed. No injury or release was reported.",report_type="Unsafe Condition"),
 dict(name="H2S Mock Drill",description="H2S emergency mock drill was conducted successfully. The gas detector was tested and found functional. No actual gas release occurred.",report_type="Incident"),
 dict(name="Vague Report",description="Unsafe condition observed near equipment.",report_type="Unsafe Condition"),
 dict(name="Pipeline Excavation",description="Excavation work was observed close to a marked pipeline route. Permit details and underground line verification were not available.",report_type="Unsafe Act"),
]
TEMPLATES=[
 SAMPLES[0]["description"],
 "A technician was inside the lifting zone beside a crane and suspended load. Exclusion zone barricade was damaged. No injury was recorded.",
 "A helper entered crane radius during lifting. A suspended pipe was moving. No injury occurred.",
 "A person crossed below the load during crane lifting activity. The exclusion zone was missing.",
 SAMPLES[1]["description"],
 "During process operation the PSV was bypassed on the separator. Personnel were near the vessel.",
 "During operation the pressure relief valve failed on the vessel. No release was recorded.",
 "Maintenance on a pump exposed a rotating shaft. Lockout was absent. No injury occurred.",
 "A technician working on an energized motor found the isolation bypassed during maintenance.",
 "Maintenance on a motor started while LOTO was not verified. No injury was recorded.",
 SAMPLES[4]["description"],
 "Trenching with an excavator was observed close to a buried pipeline. Permit details were not available.",
 "Excavation near a pipeline route continued. Underground line verification was unverified.",
 "Worker welding near a tank with flammable vapour reported. Hot work permit was absent.",
 "Grinding near a tank with flammable gas was observed. Gas test was not available.",
 "Worker on scaffold at a height of 8 m was exposed to an open edge. Guardrail was missing.",
 "Standing on a platform during scaffold work at 5 m. Fall protection was damaged.",
 "Worker exposed to H2S during gas testing. Gas detector failed.",
 "H2S monitoring reported 12 ppm. Gas detector calibration expired.",
 "Worker entered a tank for confined space work. Entry permit was absent. Oxygen deficiency was reported.",
 "Driving a truck, driver speeding with a pedestrian behind. Pedestrian barrier was missing.",
 "Well control during drilling recorded a well kick. BOP was bypassed. Crew on rig were present.",
 SAMPLES[2]["description"],
 "Gas detector installed for H2S monitoring. Detector condition is unknown.",
 SAMPLES[3]["description"],
 "Housekeeping observation reported at the workshop. Waste packaging was moved to a bin.",
 "Emergency drill simulated a confined space rescue. No actual release occurred. Atmosphere test tested successfully.",
]
def demo_reports():
    sites=["Duliajan · Demo","Moran · Demo","Naharkatiya · Demo","Digboi · Demo"]
    now=datetime.now(timezone.utc)
    for i in range(80):
        index=i%len(TEMPLATES)
        # Deterministic varied dates create inspectable historical trend windows.
        age=(i*7)%55+1 if index>3 else (i*3)%25+1
        yield dict(report_id=f"DEMO-{i+1:03}",site=sites[(i//3)%len(sites)],department="Operations" if i%3 else "Maintenance",
            report_type=["Near Miss","Unsafe Condition","Unsafe Act","Incident"][i%4],
            event_timestamp=(now-timedelta(days=age,hours=i%8)).isoformat(),description=TEMPLATES[index],
            immediate_action="Reported to the site HSE team for review.",is_synthetic=True,
            source_system="SYNTHETIC_DEMO",source_record_id=f"DEMO-{i+1:03}")
