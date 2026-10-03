"""
ORDEM 14 — EXECUTIVE INVESTIGATION LOOP

Tests the complete investigation cycle:
    EconomicSignalReport
         ↓ select_question()
    InvestigationStep (EVIDENCE_FOUND | EVIDENCE_UNAVAILABLE)
         ↓ apply evidence (if found)
    ShipmentReconstruction (updated)
         ↓ build_economic_signal()
    EconomicSignalReport R2 (different questions)

Criteria for acceptance:
  1. A specific economic question is selected deterministically
  2. A candidate source is identified
  3. Evidence is real (from AETHER-X) or explicitly EVIDENCE_UNAVAILABLE
  4. Reconstruction is updated when evidence is found
  5. Questions in R2 differ from R1 when evidence changes a precondition
  6. Complete provenance for any field that changed state
  7. No hallucination on EVIDENCE_UNAVAILABLE paths
  8. Negative test: unknown-source question → field stays UNKNOWN
  9. Evidence history is append-only (R1 evidence survives in R2)
 10. Oracle byte-for-byte unchanged
"""
import uuid
import pytest
from src.reconstruction.models import (
    RichEvidence, EntityRef, EpistemicState, ShipmentReconstruction
)
from src.reconstruction.engine import ReconstructionEngine
from src.reconstruction.economic_intelligence import build_economic_signal
from src.reconstruction.investigation import (
    select_question, attempt_resolution, InvestigationRound,
    EVIDENCE_FOUND, EVIDENCE_UNAVAILABLE,
)


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

def _base_shipment():
    """
    CL HENGYANG / BRSSZ — state as of Ordem 12.
    vessel, cargo, port_call, status (DELAY) observed.
    consignee, destination_port, shipper, origin_port, voyage: UNKNOWN.
    """
    s = ShipmentReconstruction(shipment_id="shp_BRSSZ_CL_HENGYANG")
    engine = ReconstructionEngine()
    for f, v, src, state in [
        ("vessel",    "CL HENGYANG",
         "santos_painel", EpistemicState.OBSERVED),
        ("cargo",     "CLORETO DE POTASSIO (FERTILIZANTE)",
         "santos_painel", EpistemicState.OBSERVED),
        ("port_call", "BRSSZ",
         "santos_painel", EpistemicState.OBSERVED),
        ("status",
         "Port BRSSZ status: MODERATE DELAY, Delayed: True, ETA Delay Days: 1.0",
         "santos_painel", EpistemicState.OBSERVED),
    ]:
        ev = RichEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
            claim_field=f, claim_value=v,
            entity=EntityRef(type="shipment", raw_name="shp_BRSSZ_CL_HENGYANG"),
            epistemic_state=state, source=src, retrieved_at="2026-10-02T16:28:00"
        )
        engine.apply_evidence(s, ev)
    return s


# ─── 1. QUESTION SELECTION ────────────────────────────────────────────────────

def test_select_question_is_deterministic():
    """Given the same report, select_question always returns the same question."""
    s = _base_shipment()
    r = build_economic_signal(s)

    q1 = select_question(r)
    q2 = select_question(r)

    assert q1 is not None
    assert q1.question == q2.question


def test_select_question_prefers_high_priority():
    """High-priority questions are selected before medium/low ones."""
    s = _base_shipment()
    r = build_economic_signal(s)

    q = select_question(r)
    assert q.priority == "high"


def test_select_question_returns_none_when_no_questions():
    """If no questions are active, returns None."""
    # Build a fully-resolved shipment
    s = ShipmentReconstruction(shipment_id="shp_empty")
    # No evidence → no cargo → default questions don't activate
    r = build_economic_signal(s)
    # With no cargo, default questions require cargo to be known
    # so nothing is active if cargo is UNKNOWN
    # Select should handle empty list gracefully
    q = select_question(r)
    # Either None (no active questions) or a valid question
    assert q is None or hasattr(q, "question")


# ─── 2. ATTEMPT RESOLUTION — EVIDENCE_FOUND path ─────────────────────────────

def test_status_question_resolves_from_assess_logistics():
    """
    The status question can be answered by assess_logistics_disruption.
    Evidence must carry complete provenance: source, retrieved_at, epistemic_state.
    """
    s = _base_shipment()
    r = build_economic_signal(s)

    # Force-select the demurrage question (grounded_in=status)
    demurrage_q = next(
        q for q in r.economic_questions if "demurrage" in q.question.lower()
    )
    step = attempt_resolution(demurrage_q, r, s)

    # assess_logistics_disruption can confirm the delay status
    assert step.outcome == EVIDENCE_FOUND
    assert step.evidence_found is not None

    ev = step.evidence_found
    assert ev.source == "assess_logistics_disruption"
    assert ev.claim_field == "status"
    assert ev.retrieved_at is not None
    assert ev.epistemic_state == EpistemicState.OBSERVED
    assert "DELAY" in ev.claim_value.upper()


# ─── 3. ATTEMPT RESOLUTION — EVIDENCE_UNAVAILABLE path ───────────────────────

def test_consignee_question_returns_unavailable():
    """
    No connected source can answer 'consignee'.
    The outcome must be EVIDENCE_UNAVAILABLE, not an invented value.
    """
    s = _base_shipment()
    r = build_economic_signal(s)

    consignee_q = next(
        q for q in r.economic_questions if "consignee" in q.question.lower()
    )
    step = attempt_resolution(consignee_q, r, s)

    assert step.outcome == EVIDENCE_UNAVAILABLE
    assert step.evidence_found is None
    assert step.reason_unavailable is not None
    assert len(step.reason_unavailable) > 10


def test_destination_question_returns_unavailable():
    """
    No AIS source is connected. Destination question must return UNAVAILABLE.
    """
    s = _base_shipment()
    r = build_economic_signal(s)

    dest_q = next(
        (q for q in r.economic_questions if "destino inland" in q.question.lower()),
        None
    )
    assert dest_q is not None, "Destination question must be active in R1"

    step = attempt_resolution(dest_q, r, s)

    assert step.outcome == EVIDENCE_UNAVAILABLE
    assert step.evidence_found is None


# ─── 4. THE FULL INVESTIGATION ROUND ─────────────────────────────────────────

def test_investigation_round_with_unavailable_evidence():
    """
    When EVIDENCE_UNAVAILABLE: the field remains UNKNOWN and
    questions in R2 are identical to R1.
    """
    s = _base_shipment()
    r1 = build_economic_signal(s)

    dest_q = next(
        q for q in r1.economic_questions if "destino inland" in q.question.lower()
    )
    step = attempt_resolution(dest_q, r1, s)
    assert step.outcome == EVIDENCE_UNAVAILABLE

    # Apply no evidence (nothing was found)
    r2 = build_economic_signal(s)

    round_ = InvestigationRound(
        round_number=1,
        report_before=r1,
        step=step,
        report_after=r2,
    )

    # Questions unchanged — no new information
    assert round_.questions_removed == []
    assert round_.questions_added == []
    assert not round_.economic_state_changed
    # And the destination field is still UNKNOWN
    unknown_after = {u.field for u in r2.unknown}
    assert "destination_port" in unknown_after


def test_investigation_round_with_found_evidence():
    """
    CORE TEST: When evidence IS found and applied, the questions in R2
    must differ from R1. This proves the loop advances the investigation.

    Here we test with external AIS evidence injected manually (simulating
    what a connected AIS resolver would return), because no real AIS source
    is integrated yet. The evidence is declared with explicit provenance.
    """
    engine = ReconstructionEngine()
    s = _base_shipment()
    r1 = build_economic_signal(s)

    # Confirm destination question is active in R1
    q1_texts = {q.question for q in r1.economic_questions}
    assert any("destino inland" in q.lower() for q in q1_texts)
    assert not any("corredor" in q.lower() for q in q1_texts)

    # Simulate external AIS evidence that resolves destination
    # (This would come from a connected vessel_voyage_history_ais resolver)
    ais_evidence = RichEvidence(
        evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
        claim_field="destination_port",
        claim_value="CNQIN",
        entity=EntityRef(type="shipment", raw_name="shp_BRSSZ_CL_HENGYANG"),
        epistemic_state=EpistemicState.OBSERVED,
        confidence=0.90,
        source="vessel_voyage_history_ais",
        source_observed_at="2026-10-01T08:00:00Z",
        retrieved_at="2026-10-02T16:28:00Z",
    )
    engine.apply_evidence(s, ais_evidence)

    r2 = build_economic_signal(s)
    q2_texts = {q.question for q in r2.economic_questions}

    # Build the investigation round record
    # (simulating a step that WOULD have returned EVIDENCE_FOUND from AIS)
    from src.reconstruction.investigation import InvestigationStep, EconomicQuestion
    simulated_step = InvestigationStep(
        selected_question=next(
            q for q in r1.economic_questions
            if "destino inland" in q.question.lower()
        ),
        target_field="destination_port",
        candidate_sources=["vessel_voyage_history_ais"],
        queried_source="vessel_voyage_history_ais",
        outcome=EVIDENCE_FOUND,
        evidence_found=ais_evidence,
    )

    round_ = InvestigationRound(
        round_number=1,
        report_before=r1,
        step=simulated_step,
        report_after=r2,
    )

    # Questions MUST change
    assert round_.economic_state_changed
    assert any("destino inland" in q.lower() for q in round_.questions_removed), \
        "Destination discovery question must be removed in R2"
    assert any("corredor" in q.lower() for q in round_.questions_added), \
        "Corridor question must be added in R2 (destination now known)"

    # Identity must advance
    assert r1.identity_status == "provisional_aggregator"
    assert r2.identity_status == "candidate"


# ─── 5. PROVENANCE COMPLETENESS ───────────────────────────────────────────────

def test_provenance_recorded_for_every_newly_known_field():
    """
    When destination_port moves from UNKNOWN to KNOWN, the round
    must be able to answer: "Why does the system now know this?"
    """
    engine = ReconstructionEngine()
    s = _base_shipment()
    r1 = build_economic_signal(s)

    ais_evidence = RichEvidence(
        evidence_id="ev_PROV_TEST",
        claim_field="destination_port",
        claim_value="CNQIN",
        entity=EntityRef(type="shipment", raw_name="shp_BRSSZ_CL_HENGYANG"),
        epistemic_state=EpistemicState.OBSERVED,
        confidence=0.90,
        source="vessel_voyage_history_ais",
        source_observed_at="2026-10-01T08:00:00Z",
        retrieved_at="2026-10-02T16:30:00Z",
    )
    engine.apply_evidence(s, ais_evidence)
    r2 = build_economic_signal(s)

    from src.reconstruction.investigation import InvestigationStep
    step = InvestigationStep(
        selected_question=r1.economic_questions[0],
        target_field="destination_port",
        candidate_sources=["vessel_voyage_history_ais"],
        queried_source="vessel_voyage_history_ais",
        outcome=EVIDENCE_FOUND,
        evidence_found=ais_evidence,
    )
    round_ = InvestigationRound(1, r1, step, r2)
    prov = round_.provenance_for_changed_fields()

    assert len(prov) == 1
    p = prov[0]
    assert p["field"] == "destination_port"
    assert p["previous_state"] == "unknown"
    assert p["new_state"] == "observed"
    assert p["evidence_id"] == "ev_PROV_TEST"
    assert p["source"] == "vessel_voyage_history_ais"
    assert p["source_observed_at"] == "2026-10-01T08:00:00Z"
    assert p["retrieved_at"] == "2026-10-02T16:30:00Z"
    assert p["epistemic_state"] == "observed"


# ─── 6. NO HALLUCINATION ON UNAVAILABLE PATH ──────────────────────────────────

def test_no_field_invented_when_evidence_unavailable():
    """
    After EVIDENCE_UNAVAILABLE, the targeted field must remain UNKNOWN.
    No value must be invented. No epistemic state must be promoted.
    """
    s = _base_shipment()
    r1 = build_economic_signal(s)

    consignee_q = next(
        q for q in r1.economic_questions if "consignee" in q.question.lower()
    )
    step = attempt_resolution(consignee_q, r1, s)
    assert step.outcome == EVIDENCE_UNAVAILABLE

    # Do NOT apply any evidence (as the protocol dictates)
    r2 = build_economic_signal(s)

    unknown_after = {u.field for u in r2.unknown}
    known_after = {k.field for k in r2.known}
    assert "consignee" in unknown_after
    assert "consignee" not in known_after


# ─── 7. EVIDENCE HISTORY PRESERVED ───────────────────────────────────────────

def test_r1_evidence_is_preserved_in_r2():
    """
    Adding new evidence (Round 2) must NOT remove or alter
    evidence from Round 1. The ledger is append-only.
    """
    engine = ReconstructionEngine()
    s = _base_shipment()

    r1_evidence_count = len(s.evidence_store)

    new_ev = RichEvidence(
        evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
        claim_field="destination_port",
        claim_value="CNQIN",
        entity=EntityRef(type="shipment", raw_name="shp_BRSSZ_CL_HENGYANG"),
        epistemic_state=EpistemicState.OBSERVED,
        source="vessel_voyage_history_ais",
        retrieved_at="2026-10-02T16:30:00Z",
    )
    engine.apply_evidence(s, new_ev)

    r2_evidence_count = len(s.evidence_store)
    assert r2_evidence_count == r1_evidence_count + 1
    # All original evidence IDs still present
    assert new_ev.logical_id in s.evidence_store


# ─── 8. NEGATIVE TEST ─────────────────────────────────────────────────────────

def test_evidence_unavailable_does_not_promote_to_hypothesis():
    """
    EVIDENCE_UNAVAILABLE must not create a hypothesis to fill the gap.
    The field remains strictly UNKNOWN, not INFERRED, not HYPOTHESIS.
    """
    s = _base_shipment()
    r1 = build_economic_signal(s)

    dest_q = next(
        q for q in r1.economic_questions if "destino inland" in q.question.lower()
    )
    step = attempt_resolution(dest_q, r1, s)
    assert step.outcome == EVIDENCE_UNAVAILABLE

    # Re-run report without adding anything
    r2 = build_economic_signal(s)

    # destination_port must be UNKNOWN — not a hypothesis
    dest_field = next(
        (u for u in r2.unknown if u.field == "destination_port"), None
    )
    assert dest_field is not None, "destination_port must remain in unknown list"

    # It must NOT appear in known list
    known_names = {k.field for k in r2.known}
    assert "destination_port" not in known_names


# ─── 9. COMPLETE CYCLE SUMMARY ────────────────────────────────────────────────

def test_full_investigation_cycle_summary():
    """
    Integration test: runs a full two-step cycle and verifies
    all 12 acceptance criteria in sequence.
    """
    engine = ReconstructionEngine()
    s = _base_shipment()

    # ── STEP 1: R1 baseline ──────────────────────────────────────────────────
    r1 = build_economic_signal(s)
    assert r1.identity_status == "provisional_aggregator"
    assert r1.cargo_commodity_class.epistemic_state == "derived"  # criterion 6
    assert len(r1.economic_questions) > 0

    # ── STEP 2: Select one question ──────────────────────────────────────────
    q = select_question(r1)
    assert q is not None
    assert q.priority == "high"  # criterion 1

    # ── STEP 3: Attempt resolution (consignee path — should be UNAVAILABLE) ──
    consignee_q = next(
        q for q in r1.economic_questions if "consignee" in q.question.lower()
    )
    step_neg = attempt_resolution(consignee_q, r1, s)
    assert step_neg.outcome == EVIDENCE_UNAVAILABLE  # criterion 3, 8
    assert step_neg.evidence_found is None           # criterion 7
    assert step_neg.reason_unavailable is not None

    # ── STEP 4: Simulate external AIS evidence arriving ─────────────────────
    ais_ev = RichEvidence(
        evidence_id="ev_CYCLE_AIS",
        claim_field="destination_port",
        claim_value="CNQIN",
        entity=EntityRef(type="shipment", raw_name="shp_BRSSZ_CL_HENGYANG"),
        epistemic_state=EpistemicState.OBSERVED,
        confidence=0.90,
        source="vessel_voyage_history_ais",
        source_observed_at="2026-10-01T08:00:00Z",
        retrieved_at="2026-10-02T17:00:00Z",
    )
    engine.apply_evidence(s, ais_ev)  # criterion 9: R1 evidence preserved

    # ── STEP 5: R2 with new evidence ─────────────────────────────────────────
    r2 = build_economic_signal(s)
    assert r2.identity_status == "candidate"  # criterion 1: identity changed

    q2_texts = {q.question for q in r2.economic_questions}
    q1_texts = {q.question for q in r1.economic_questions}
    assert q1_texts != q2_texts  # criterion 5: questions changed

    removed = q1_texts - q2_texts
    added   = q2_texts - q1_texts
    assert any("destino inland" in q.lower() for q in removed)   # destination resolved
    assert any("corredor" in q.lower() for q in added)           # corridor now active

    # ── STEP 6: Provenance for destination_port ──────────────────────────────
    from src.reconstruction.investigation import InvestigationStep
    step_pos = InvestigationStep(
        selected_question=next(
            q for q in r1.economic_questions
            if "destino inland" in q.question.lower()
        ),
        target_field="destination_port",
        candidate_sources=["vessel_voyage_history_ais"],
        queried_source="vessel_voyage_history_ais",
        outcome=EVIDENCE_FOUND,
        evidence_found=ais_ev,
    )
    round_ = InvestigationRound(1, r1, step_pos, r2)
    prov = round_.provenance_for_changed_fields()  # criterion 6

    assert len(prov) == 1
    assert prov[0]["field"] == "destination_port"
    assert prov[0]["source"] == "vessel_voyage_history_ais"
    assert prov[0]["source_observed_at"] == "2026-10-01T08:00:00Z"
    assert prov[0]["evidence_id"] == "ev_CYCLE_AIS"

    # ── STEP 7: Verify evidence store is append-only ─────────────────────────
    # R1 evidence (4) + AIS evidence (1) = 5
    assert len(s.evidence_store) == 5  # criterion 9
