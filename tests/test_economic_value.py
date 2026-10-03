"""
ORDEM 15 — ECONOMIC VALUE TEST

Tests that the EconomicValueAssessment correctly answers the four questions
using only what AETHER-X can observe today — with strict epistemic honesty.

Acceptance criteria:
  1. Observable facts correctly classified (OBSERVED vs ESTIMATED)
  2. estimated_daily_demurrage_usd is ESTIMATED, never OBSERVED
  3. actual_demurrage_paid never appears — not in the model
  4. Calculable impacts carry caveats and not_equivalent_to
  5. Decisions reference roles, never company names
  6. Missing fields correctly identified as commercial gaps
  7. Readiness level matches the evidence state
  8. When consignee is known, readiness upgrades to "identified"
  9. Full serialization integrity
 10. Negative: model estimate NOT promoted to observed fact
"""
import pytest
import uuid
import json
from src.reconstruction.models import (
    RichEvidence, EntityRef, EpistemicState, ShipmentReconstruction
)
from src.reconstruction.engine import ReconstructionEngine
from src.reconstruction.economic_value import (
    assess_economic_value, EconomicValueAssessment,
    ObservableFact, CalculableImpact, OperationalDecision, MissingForCommercial,
)


# ─── FIXTURE ──────────────────────────────────────────────────────────────────

def _make_shipment(extras=None):
    s = ShipmentReconstruction(shipment_id="shp_BRSSZ_CL_HENGYANG")
    e = ReconstructionEngine()
    base = [
        ("vessel",    "CL HENGYANG",
         "santos_painel", EpistemicState.OBSERVED),
        ("cargo",     "CLORETO DE POTASSIO (FERTILIZANTE)",
         "santos_painel", EpistemicState.OBSERVED),
        ("port_call", "BRSSZ",
         "santos_painel", EpistemicState.OBSERVED),
        ("status",
         "Port BRSSZ status: MODERATE DELAY, Delayed: True, ETA Delay Days: 1.0",
         "santos_painel", EpistemicState.OBSERVED),
    ]
    for f, v, src, st in base + (extras or []):
        ev = RichEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
            claim_field=f, claim_value=v,
            entity=EntityRef(type="shipment", raw_name="shp_BRSSZ_CL_HENGYANG"),
            epistemic_state=st, source=src, retrieved_at="2026-10-02T16:28:00"
        )
        e.apply_evidence(s, ev)
    return s


# ─── Q1: OBSERVABLE FACTS ─────────────────────────────────────────────────────

def test_observed_facts_are_present():
    """Vessel, cargo, port_call, status from the reconstruction must appear."""
    a = assess_economic_value(_make_shipment())
    fact_fields = {f.field for f in a.observable_facts}
    assert "vessel" in fact_fields
    assert "cargo" in fact_fields
    assert "port_call" in fact_fields
    assert "operational_status" in fact_fields


def test_port_risk_facts_are_estimated_not_observed():
    """
    eta_delay_days and estimated_daily_demurrage_usd come from the port_risk
    parametric model. They must be labelled ESTIMATED, never OBSERVED.
    """
    a = assess_economic_value(_make_shipment())
    fact_map = {f.field: f for f in a.observable_facts}

    assert "eta_delay_days" in fact_map
    assert fact_map["eta_delay_days"].epistemic_state == "estimated"

    assert "estimated_daily_demurrage_usd" in fact_map
    assert fact_map["estimated_daily_demurrage_usd"].epistemic_state == "estimated"


def test_no_observed_fact_is_labelled_estimated():
    """
    Conversely: facts captured directly from the operational layer
    (lineup, status) must not be downgraded to estimated.
    """
    a = assess_economic_value(_make_shipment())
    directly_observed = {"vessel", "cargo", "port_call", "operational_status"}
    fact_map = {f.field: f for f in a.observable_facts}
    for field_name in directly_observed:
        if field_name in fact_map:
            assert fact_map[field_name].epistemic_state == "observed", \
                f"Field '{field_name}' should be observed, not estimated"


# ─── Q2: CALCULABLE IMPACTS ───────────────────────────────────────────────────

def test_demurrage_impact_is_present_when_delay_confirmed():
    a = assess_economic_value(_make_shipment())
    demurrage = [i for i in a.calculable_impacts if "demurrage" in i.impact_type]
    assert len(demurrage) >= 1


def test_demurrage_impact_is_estimated_not_observed():
    """CRITICAL: demurrage impact must be ESTIMATED. Never OBSERVED."""
    a = assess_economic_value(_make_shipment())
    for impact in a.calculable_impacts:
        if "demurrage" in impact.impact_type:
            assert impact.epistemic_state in ("estimated", "derived"), \
                f"Demurrage impact must not be 'observed'. Got: {impact.epistemic_state}"


def test_demurrage_impact_has_not_equivalent_to():
    """The impact must explicitly state it is NOT actual_demurrage_paid."""
    a = assess_economic_value(_make_shipment())
    for impact in a.calculable_impacts:
        if "demurrage" in impact.impact_type:
            assert impact.not_equivalent_to == "actual_demurrage_paid", \
                "Demurrage impact must explicitly state not_equivalent_to=actual_demurrage_paid"


def test_demurrage_impact_has_caveats():
    """Every demurrage impact must carry non-empty caveats."""
    a = assess_economic_value(_make_shipment())
    for impact in a.calculable_impacts:
        if "demurrage" in impact.impact_type:
            assert len(impact.caveats) >= 2, "Demurrage impact requires multiple caveats"


def test_demurrage_impact_has_numeric_value():
    """With delay confirmed and port_risk available, a USD value must be produced."""
    a = assess_economic_value(_make_shipment())
    demurrage = next(
        (i for i in a.calculable_impacts if i.value is not None and "demurrage" in i.impact_type),
        None
    )
    assert demurrage is not None
    assert isinstance(demurrage.value, (int, float))
    assert demurrage.value > 0
    assert demurrage.unit == "USD"


def test_no_demurrage_impact_without_delay():
    """Without a confirmed delay, no demurrage impact is calculated."""
    s = ShipmentReconstruction(shipment_id="shp_no_delay")
    e = ReconstructionEngine()
    for f, v, src, st in [
        ("vessel", "CL HENGYANG", "src", EpistemicState.OBSERVED),
        ("cargo", "CLORETO DE POTASSIO (FERTILIZANTE)", "src", EpistemicState.OBSERVED),
        ("port_call", "BRSSZ", "src", EpistemicState.OBSERVED),
        ("status", "Port BRSSZ status: NORMAL, Delayed: False", "src", EpistemicState.OBSERVED),
    ]:
        ev = RichEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}", claim_field=f, claim_value=v,
            entity=EntityRef(type="shipment", raw_name="shp_no_delay"),
            epistemic_state=st, source=src, retrieved_at="2026"
        )
        e.apply_evidence(s, ev)
    a = assess_economic_value(s)
    demurrage = [i for i in a.calculable_impacts if "demurrage_exposure_estimate" in i.impact_type]
    assert len(demurrage) == 0


# ─── Q3: ACTIONABLE DECISIONS ─────────────────────────────────────────────────

def test_decisions_are_role_based_not_company_names():
    """
    No decision may name a specific company.
    All applicable_roles must be generic economic roles.
    """
    a = assess_economic_value(_make_shipment())
    assert len(a.actionable_decisions) > 0

    forbidden_company_indicators = [
        "vale", "petrobras", "cargill", "adm", "bunge",
        "maersk", "msc", "cma cgm", "cosco", "yang ming",
    ]
    for decision in a.actionable_decisions:
        decision_text = decision.decision.lower()
        for company in forbidden_company_indicators:
            assert company not in decision_text, \
                f"Decision must not name company '{company}'"
        for role in decision.applicable_roles:
            for company in forbidden_company_indicators:
                assert company not in role.lower(), \
                    f"Role must not be a company name: '{role}'"


def test_decisions_have_certainty_levels():
    """All decisions must declare a certainty level."""
    a = assess_economic_value(_make_shipment())
    valid_levels = {"signal_only", "partial_context", "actionable"}
    for d in a.actionable_decisions:
        assert d.certainty_level in valid_levels


def test_decisions_declare_what_would_upgrade_certainty():
    """Each decision must state what additional evidence would increase certainty."""
    a = assess_economic_value(_make_shipment())
    for d in a.actionable_decisions:
        assert len(d.requires_for_higher_certainty) > 0


# ─── Q4: MISSING FOR COMMERCIAL SIGNAL ───────────────────────────────────────

def test_consignee_identified_as_commercial_gap():
    """Without consignee, it must appear in missing_for_commercial."""
    a = assess_economic_value(_make_shipment())
    gap_fields = {g.field for g in a.missing_for_commercial}
    assert "consignee" in gap_fields


def test_destination_identified_as_commercial_gap():
    a = assess_economic_value(_make_shipment())
    gap_fields = {g.field for g in a.missing_for_commercial}
    assert "destination_port" in gap_fields


def test_gaps_have_candidate_sources():
    """Every commercial gap must declare which sources could fill it."""
    a = assess_economic_value(_make_shipment())
    for g in a.missing_for_commercial:
        assert len(g.candidate_sources) > 0, \
            f"Gap '{g.field}' has no candidate sources"


# ─── READINESS LEVELS ─────────────────────────────────────────────────────────

def test_readiness_is_signal_only_without_consignee_or_destination():
    a = assess_economic_value(_make_shipment())
    assert a.commercial_readiness == "signal_only"
    assert len(a.readiness_explanation) > 10


def test_readiness_upgrades_to_candidate_when_destination_known():
    a = assess_economic_value(_make_shipment(extras=[
        ("destination_port", "CNQIN", "ais", EpistemicState.OBSERVED),
    ]))
    assert a.commercial_readiness == "candidate"


def test_readiness_upgrades_to_identified_when_consignee_known():
    a = assess_economic_value(_make_shipment(extras=[
        ("consignee", "AGRI_CORP_SA", "bill_of_lading", EpistemicState.OBSERVED),
    ]))
    assert a.commercial_readiness == "identified"


# ─── NEGATIVE: NO HALLUCINATION ───────────────────────────────────────────────

def test_model_estimate_never_promoted_to_observed():
    """
    The parametric model value from get_port_risk() must NEVER appear
    as epistemic_state='observed' anywhere in the assessment.
    """
    a = assess_economic_value(_make_shipment())
    d = a.as_dict()
    for fact in d["observable_facts"]:
        if fact["field"] in ("estimated_daily_demurrage_usd", "eta_delay_days"):
            assert fact["epistemic_state"] != "observed", \
                f"Model estimate '{fact['field']}' must not be labelled 'observed'"
    for impact in d["calculable_impacts"]:
        assert impact["epistemic_state"] != "observed", \
            "No calculable impact may claim to be 'observed'"


def test_actual_demurrage_paid_never_appears():
    """
    The field 'actual_demurrage_paid' must never appear in any
    part of the assessment output. It is unknowable from current sources.
    """
    a = assess_economic_value(_make_shipment())
    full_json = json.dumps(a.as_dict())
    # 'not_equivalent_to' referencing it is fine — that's the warning
    # But it must not appear as a value or fact field name
    assert full_json.count("actual_demurrage_paid") <= len(a.calculable_impacts), \
        "actual_demurrage_paid may only appear in not_equivalent_to fields"


# ─── SERIALIZATION ────────────────────────────────────────────────────────────

def test_full_assessment_serializes():
    a = assess_economic_value(_make_shipment())
    d = a.as_dict()
    j = json.dumps(d, ensure_ascii=False)
    assert len(j) > 200
    assert "observable_facts" in d
    assert "calculable_impacts" in d
    assert "actionable_decisions" in d
    assert "missing_for_commercial" in d
    assert "commercial_readiness" in d
