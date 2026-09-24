"""Evidence-preserving prototype extraction; assertions are separated from context."""
import re
from ml.catalogue import FAMILIES

NEGATION = re.compile(
    r"\b(?:no|not|never|without|neither)\s+"
    r"(?:(?:a|an|any|actual|worker|workers|person|personnel|rigger|riggers|"
    r"mechanic|mechanics|fitter|technician|operator|helper|was|were|is|are|"
    r"has|had|been|being|found|observed|seen|reported|ever)\s+){0,6}$", re.I
)
STATE_PATTERNS = [
    ("BYPASSED", r"\b(?:gagged|bypassed|disabled|defeated)\b"),
    ("ABSENT", r"\b(?:absent|missing|removed|taken down|"
     r"(?:not|never) (?:been )?(?:installed|provided|erected|established|barricaded|cordoned(?: off)?)|"
     r"no (?:lockout|loto|harness|guardrail|permit|spotter|barricade|cordon))\b"),
    ("FAILED", r"\b(?:failed|inoperative|not functional|did not operate)\b"),
    ("DEGRADED", r"\b(?:degraded|damaged|expired|overdue|leaking)\b"),
    ("UNVERIFIED", r"\b(?:not available|unavailable|not verified|unverified|not tested|not recorded|unknown)\b"),
    ("EFFECTIVE", r"\b(?:tested and (?:found )?functional|tested successfully|verified effective|function tested successfully)\b"),
]
BOUNDARY = re.compile(r"[;\n]|(?<!\d)[.!?](?=\s|$)")
EDUCATION = re.compile(r"\b(?:classroom|training briefing|safety briefing|training material|tabletop|lesson)\b", re.I)
DISCUSSION = re.compile(r"\b(?:discussed|described|explained|reviewed|illustrated|covered|exercise|example)\b", re.I)
ACTUAL = re.compile(r"\b(?:actually|real (?:release|leak|exposure|incident)|occurred|observed)\b", re.I)
CONDITIONAL = re.compile(r"\b(?:if|unless|would|could|might|should|must|hypothetical|imagined|simulated)\b", re.I)


def sentences(text):
    start = 0
    for end in BOUNDARY.finditer(text):
        yield start, end.start()
        start = end.end()
    if start < len(text):
        yield start, len(text)


def sentence_at(text, position):
    return next(((a, b) for a, b in sentences(text) if a <= position <= b), (0, len(text)))


def assertion_context(match, text):
    left, right = sentence_at(text, match.start())
    statement = text[left:right]
    # A contrast starts a new assertion, e.g. "if X ... but the detector actually failed".
    prefix = re.split(r"\b(?:but|however)\b|,", text[left:match.start()], flags=re.I)[-1]
    if NEGATION.search(prefix[-100:]):
        return "NEGATED"
    if CONDITIONAL.search(prefix) and not ACTUAL.search(prefix):
        return "HYPOTHETICAL"
    if EDUCATION.search(statement) and DISCUSSION.search(statement) and not ACTUAL.search(statement):
        return "HYPOTHETICAL"
    return "AFFIRMED"


def affirmed_matches(pattern, text):
    for match in re.finditer(pattern, text, re.I):
        if assertion_context(match, text) == "AFFIRMED":
            yield match


def extract(description):
    spans, contextual = [], []
    barriers, equipment, hazards, exposures, consequences, rules = [], [], [], [], [], []
    active = []
    negated_exposure = False

    def evidence(match, label, source="dictionary"):
        value = dict(text=match.group(), label=label, start_offset=match.start(),
                     end_offset=match.end(), source_type=source,
                     confidence=1.0 if source == "regex" else 0.85)
        if value not in spans:
            spans.append(value)

    def assertions(pattern, label):
        found = []
        for match in re.finditer(pattern, description, re.I):
            status = assertion_context(match, description)
            if status == "AFFIRMED":
                found.append(match)
            else:
                item = dict(text=match.group(), label=label, assertion=status,
                            start_offset=match.start(), end_offset=match.end())
                if item not in contextual:
                    contextual.append(item)
        return found

    for family in FAMILIES:
        hm = assertions(family["hazard_re"], "HAZARD")
        am = assertions(family["activity_re"], "ACTIVITY")
        if hm or am:
            active.append((family, hm, am))

    # Generic words such as "permit" may only own a state within an active family.
    mentions = [(m.start(), m.end(), f["id"]) for f, _, _ in active
                for m in re.finditer(f["barrier_re"], description, re.I)]
    segments = list(sentences(description))

    for family, hm, am in active:
        em = assertions(family["exposure_re"], "EXPOSURE")
        if family["id"] == "P-001":
            em = [m for m in em if not re.match(r"^(?:was|were|is|remained)\b", m.group(), re.I)
                  or re.search(r"\b(?:worker|person|mechanic|fitter|rigger|technician|helper|operator|crew|he|she|they)\b",
                               description[max(0, m.start()-50):m.start()], re.I)]
        negated_exposure |= any(e["label"] == "EXPOSURE" and e["assertion"] == "NEGATED" for e in contextual)
        qm = assertions(family["equipment_re"], "EQUIPMENT")
        bm = list(re.finditer(family["barrier_re"], description, re.I))
        for label, values in [("ACTIVITY", am), ("HAZARD", hm), ("EXPOSURE", em),
                              ("EQUIPMENT", qm), ("BARRIER", bm)]:
            for match in values:
                if assertion_context(match, description) == "AFFIRMED":
                    evidence(match, label)
        if hm:
            hazards.append(family["hazard"])
        equipment.extend(m.group() for m in qm)
        if em:
            exposures.append("Worker in Line of Fire" if family["id"] == "P-001"
                             else "Reported proximity / direct exposure")

        scopes = {sentence_at(description, m.start()) for m in bm}
        # Resolve only an adjacent, explicit device reference with one possible antecedent.
        for index, (left, right) in enumerate(segments):
            if index == 0:
                continue
            previous = segments[index-1]
            owners = {fid for a, _, fid in mentions if previous[0] <= a < previous[1]}
            reference = r"\s*(?:it|the device|this device)\b"
            if family["id"] == "P-003":
                reference = r"\s*(?:it|the valve|this valve|the device)\b"
            if owners == {family["id"]} and re.match(reference, description[left:right], re.I):
                scopes.add((left, right))

        states, state_evidence = [], []
        present = False
        for left, right in sorted(scopes):
            statement = description[left:right]
            for match in re.finditer(r"\b(?:installed|present|in place)\b", description[left:right], re.I):
                # Evaluate in full-text coordinates, preserving sentence context.
                absolute = re.compile(re.escape(match.group()), re.I).search(description, left+match.start(), left+match.end())
                present |= absolute is not None and assertion_context(absolute, description) == "AFFIRMED"
            for state, pattern in STATE_PATTERNS:
                for candidate in re.finditer(pattern, description, re.I):
                    if not left <= candidate.start() < right:
                        continue
                    context = assertion_context(candidate, description)
                    if context != "AFFIRMED":
                        item = dict(text=candidate.group(), label="BARRIER_STATE", assertion=context,
                                    start_offset=candidate.start(), end_offset=candidate.end())
                        if item not in contextual:
                            contextual.append(item)
                        continue
                    prior = [m for m in mentions if left <= m[0] <= candidate.start()]
                    owner = max(prior, key=lambda m: (m[1], m[1]-m[0]))[2] if prior else family["id"]
                    if owner != family["id"]:
                        continue
                    states.append(state)
                    state_evidence.append(dict(text=statement.strip(), state=state))
                    evidence(candidate, "BARRIER_STATE", "regex")
        contradiction = "EFFECTIVE" in states and any(s in states for s in ["BYPASSED", "FAILED", "ABSENT", "DEGRADED"])
        state = next((s for s in ["BYPASSED", "FAILED", "ABSENT", "DEGRADED", "UNVERIFIED", "EFFECTIVE"] if s in states), "UNKNOWN")
        inferred = False
        if family["id"] == "P-001" and em and state in ["UNKNOWN", "EFFECTIVE"]:
            contradiction |= state == "EFFECTIVE"
            state, inferred = "DEGRADED", True
        verification = "PRESENT" if bm and (present or state not in ["UNKNOWN", "UNVERIFIED", "ABSENT"]) else "UNVERIFIED"
        if state == "ABSENT":
            verification = "ABSENT"
        state_quote = next((e["text"] for e in state_evidence if e["state"] == state), "")
        barriers.append(dict(
            name=family["barrier"], state=state, critical=True, threat=family["threat"],
            verification_status=verification,
            validation_status="VALIDATED" if state == "EFFECTIVE" and not contradiction else "NOT_VALIDATED",
            evidence=em[0].group() if inferred else state_quote or (bm[0].group() if bm else ""),
            confidence=0.75 if inferred else 0.9 if states else 0.0,
            match_method="exposure_inference" if inferred else "scoped_phrase_match",
            inferred=inferred, contradictory=contradiction))
        rules.extend(family["rules"])
        if hm and (em or state in ["FAILED", "BYPASSED", "ABSENT"]):
            consequences.append(family["consequence"])

    drill = bool(re.search(r"\b(?:mock drill|emergency drill|simulation)\b", description, re.I))
    no_release = bool(re.search(r"\bno actual (?:gas )?release (?:occurred|was reported)\b", description, re.I))
    adverse = bool(exposures) or any(b["state"] in ["BYPASSED", "ABSENT", "FAILED", "DEGRADED"] for b in barriers)
    context_only = bool(EDUCATION.search(description) and DISCUSSION.search(description) and not active)
    simulated = (drill and no_release and not adverse) or context_only
    if simulated:
        rules, consequences, exposures = [], [], []
    measurements = []
    for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*[- ]?\s*(tonnes?|tons?|kg|psi|bar|kPa|MPa|ppm|%LEL|metres?|meters?|m|ft|degC|°C)\b", description, re.I):
        evidence(match, "MEASUREMENT", "regex")
        measurements.append(dict(value=float(match.group(1)), unit=match.group(2), text=match.group()))
    missing = []
    if not hazards and not simulated:
        missing.append("hazard")
    if not exposures and not simulated and not negated_exposure:
        missing.append("exposure")
    if not equipment and not context_only:
        missing.append("equipment condition")
    if not context_only and (not barriers or any(b["state"] in ["UNKNOWN", "UNVERIFIED"] for b in barriers)):
        missing.append("barrier status")
    if any(b["contradictory"] for b in barriers):
        missing.append("contradictory barrier evidence")
    return dict(
        activity="Training / Hypothetical" if context_only else "Emergency Drill" if simulated else active[0][0]["activity"] if active else "Not identified",
        equipment=list(dict.fromkeys(equipment)), hazards=list(dict.fromkeys(hazards)),
        exposures=list(dict.fromkeys(exposures)), potential_consequences=list(dict.fromkeys(consequences)),
        consequence_source="inferred from hazard and exposure / barrier",
        barriers=barriers, iogp_rules=list(dict.fromkeys(rules)), measurements=measurements,
        evidence_spans=sorted(spans, key=lambda s: (s["start_offset"], s["end_offset"])),
        contextual_mentions=sorted(contextual, key=lambda s: (s["start_offset"], s["end_offset"])),
        exposure_status="SIMULATED" if simulated else "REPORTED" if exposures else "EXPLICITLY_NEGATED" if negated_exposure else "NOT_REPORTED",
        missing_information=missing, sufficiency_status="REVIEW_REQUIRED" if missing else "SUFFICIENT",
        simulated=simulated, context_only=context_only, family_ids=[f["id"] for f, _, _ in active],
        credible_fatal=bool(consequences), direct_exposure=bool(exposures),
        severe_hazard=bool(hazards) and not simulated)
