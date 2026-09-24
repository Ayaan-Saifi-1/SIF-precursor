export const contextGroups = [
 {title:'Operational context',fields:[
 ['domain','Operational domain',['UNKNOWN','Well Operations','Process / Production','Pipeline / Transport','Occupational']],
 ['site_id','Site reference'],['asset_id','Asset reference'],['equipment_refs','Equipment references'],['well_id','Well reference'],
 ['pipeline_section','Pipeline section'],['work_order','Job / work order'],['event_id','Related event ID'],['location','Exact location'],
 ['shift','Shift',['UNKNOWN','Day','Night','Extended hours']],['workforce','Workforce',['UNKNOWN','Employee','Contractor','Mixed']]]},
 {title:'Reported safety facts',fields:[
 ['reported_activity','Activity'],['reported_hazard','Hazard / energy'],['reported_threat','Threat / release mechanism'],
 ['reported_exposure','Exposure pathway'],['reported_consequence','Credible potential consequence'],
 ['actual_consequence','Actual outcome'],['barrier_name','Critical barrier'],['barrier_state','Barrier state',['UNKNOWN','UNVERIFIED','EFFECTIVE','DEGRADED','FAILED','BYPASSED','ABSENT']],
 ['barrier_evidence','Barrier condition evidence'],['verification_status','Control presence',['UNKNOWN','UNVERIFIED','PRESENT','ABSENT']],
 ['validation_status','Control effectiveness',['UNKNOWN','NOT_VALIDATED','VALIDATED']]]},
 {title:'Measurements and exposure',fields:[
 ['pressure','Pressure and unit'],['gas_concentration','Gas concentration and unit'],['height','Height and unit'],
 ['distance','Distance and unit'],['temperature','Temperature and unit'],['voltage','Voltage and unit'],
 ['mass','Load mass and unit'],['velocity','Speed and unit'],['inventory','Process inventory and unit'],
 ['sidpp','SIDPP and unit'],['pit_gain','Pit gain and unit'],['flow_change','Flow change'],
 ['mud_barrier_status','Mud / well barrier status'],['exposure_denominator','Exposure count and basis (lifts / hours / km)']]},
 {title:'Task and organisational context',fields:[
 ['task_training','Task training',['UNKNOWN','Valid','Expired','Not required']],
 ['authorization_scope','Certification / authorisation scope'],['authorization_validity','Authorisation validity'],
 ['task_familiarity','Task familiarity',['UNKNOWN','First time','Changed task','Recently performed']],
 ['equipment_familiarity','Equipment / site familiarity'],['supervision','Supervision'],
 ['pre_job_plan','Pre-job briefing / JSA'],['fatigue','Fatigue / extended hours'],
 ['change_from_plan','Change from plan'],['stop_work','Stop-work execution'],['handover','Handover'],
 ['productivity_pressure','Productivity pressure'],['procedure_quality','Procedure quality'],['staffing','Staffing context']]}
] as const;
