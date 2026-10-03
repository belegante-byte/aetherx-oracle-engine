"""
ORDEM 13.1 — Corrected tests for Economic Intelligence Layer.

Covers:
  - commodity_class carries epistemic_state=DERIVED (never OBSERVED)
  - economic_questions are active only when preconditions are met
  - questions disappear when their required-unknown field becomes known
  - new questions appear only when their required-known fields are satisfied
  - would_unlock contains only modeled fields that are currently UNKNOWN
  - external fields are separated from would_unlock
  - serialization is intact
"""
import pytest
import uuid
import json
from src.reconstruction.models import RichEvidence, EntityRef, EpistemicState, ShipmentReconstruction
from src.reconstruction.engine import ReconstructionEngine
from src.reconstruction.economic_intelligence import build_economic_signal, EconomicSignalReport


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

def _make_shipment(*evidence_tuples):
    """Build a ShipmentReconstruction from (field, value, source, state) tuples."""
    s = ShipmentReconstruction(shipment_id="shp_BRSSZ_CL_HENGYANG")
    engine = ReconstructionEngine()
    for field, val, src, state in evidence_tuples:
        ev = RichEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
            claim_field=field, claim_value=val,
            entity=EntityRef(type="shipment", raw_name="shp_BRSSZ_CL_HENGYANG"),
            epistemic_state=state, source=src, retrieved_at="2026-10-02T16:28:00"
        )
        engine.apply_evidence(s, ev)
    return s


_BASE_EVIDENCE = [
    ("vessel",    "CL HENGYANG",                                    "santos_painel",  EpistemicState.OBSERVED),
    ("cargo",     "CLORETO DE POTASSIO (FERTILIZANTE)",             "santos_painel",  EpistemicState.OBSERVED),
    ("port_call", "BRSSZ",                                          "santos_painel",  EpistemicState.OBSERVED),
    ("status",    "Port BRSSZ status: MODERATE DELAY, Delayed: True, ETA Delay Days: 1.0",
                                                                     "operational_order", EpistemicState.OBSERVED),
]


# ─── 1. COMMODITY CLASS EPISTEMIC STATE ───────────────────────────────────────

def test_commodity_class_is_derived_never_observed():
    """commodity_class must carry epistemic_state=derived, not observed."""
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    assert r.cargo_commodity_class.epistemic_state == "derived"
    assert r.cargo_commodity_class.derived_from == "cargo"
    assert r.cargo_commodity_class.value == "agricultural_input"


def test_commodity_class_unknown_cargo_gives_unknown_class():
    """Without cargo evidence, commodity_class must be unknown (still DERIVED)."""
    s = _make_shipment(
        ("vessel",    "CL HENGYANG", "santos_painel", EpistemicState.OBSERVED),
        ("port_call", "BRSSZ",       "santos_painel", EpistemicState.OBSERVED),
    )
    r = build_economic_signal(s)

    assert r.cargo_commodity_class.value == "unknown"
    assert r.cargo_commodity_class.epistemic_state == "derived"


def test_commodity_class_serializes_with_epistemic_state():
    """Serialized report must include commodity_class as object, not bare string."""
    s = _make_shipment(*_BASE_EVIDENCE)
    d = build_economic_signal(s).as_dict()

    cc = d["cargo_commodity_class"]
    assert isinstance(cc, dict)
    assert cc["epistemic_state"] == "derived"
    assert cc["derived_from"] == "cargo"
    assert "value" in cc


# ─── 2. QUESTION PRECONDITIONS ────────────────────────────────────────────────

def test_destination_question_active_when_destination_unknown():
    """When destination_port is UNKNOWN, the question 'Qual é o destino inland?' must be present."""
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    destination_qs = [q for q in r.economic_questions if "destino" in q.question.lower()]
    assert len(destination_qs) >= 1


def test_destination_question_disappears_when_destination_known():
    """
    FUNDAMENTAL TEST: When destination_port becomes OBSERVED, the discovery
    question must disappear. The investigation moves forward.
    """
    s_without_dest = _make_shipment(*_BASE_EVIDENCE)
    r1 = build_economic_signal(s_without_dest)
    q1_dest = {q.question for q in r1.economic_questions if "destino inland" in q.question.lower()}

    s_with_dest = _make_shipment(
        *_BASE_EVIDENCE,
        ("destination_port", "CNQIN", "ais_voyage_history", EpistemicState.OBSERVED),
    )
    r2 = build_economic_signal(s_with_dest)
    q2_dest = {q.question for q in r2.economic_questions if "mt/go/ms" in q.question.lower()}

    # The destination discovery question must be gone in R2
    assert len(q1_dest) >= 1, "R1 must have destination question"
    assert len(q2_dest) == 0, "R2 must NOT have destination question (it is now KNOWN)"


def test_corridor_question_requires_destination_to_be_known():
    """
    The corridor question ('Qual corredor logístico...') must NOT appear
    while destination_port is UNKNOWN — it has no factual basis.
    """
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    corridor_qs = [q for q in r.economic_questions if "corredor" in q.question.lower()]
    assert len(corridor_qs) == 0, "Corridor question must not appear without known destination"


def test_corridor_question_appears_after_destination_known():
    """
    After destination_port becomes OBSERVED, the corridor question
    becomes active (we have both endpoints).
    """
    s = _make_shipment(
        *_BASE_EVIDENCE,
        ("destination_port", "CNQIN", "ais_voyage_history", EpistemicState.OBSERVED),
    )
    r = build_economic_signal(s)

    corridor_qs = [q for q in r.economic_questions if "corredor" in q.question.lower()]
    assert len(corridor_qs) >= 1, "Corridor question must appear when destination is known"


def test_cambial_question_absent_without_consignee_and_destination():
    """
    The FX/cambial exposure question requires consignee + destination_port.
    Without them, it must NOT appear — it is not actionable.
    """
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    cambial_qs = [q for q in r.economic_questions if "cambial" in q.question.lower()]
    assert len(cambial_qs) == 0


def test_demurrage_question_appears_only_when_delay_observed():
    """The demurrage question must appear exactly because status contains DELAY."""
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    assert r.operational_delay_observed is True
    demurrage_qs = [q for q in r.economic_questions if "demurrage" in q.question.lower()]
    assert len(demurrage_qs) >= 1
    assert all(q.priority == "high" for q in demurrage_qs)


def test_demurrage_question_absent_without_delay():
    """Without a DELAY status, the demurrage question must not appear."""
    s = _make_shipment(
        ("vessel",    "CL HENGYANG",                         "santos_painel", EpistemicState.OBSERVED),
        ("cargo",     "CLORETO DE POTASSIO (FERTILIZANTE)",  "santos_painel", EpistemicState.OBSERVED),
        ("port_call", "BRSSZ",                               "santos_painel", EpistemicState.OBSERVED),
        ("status",    "Port BRSSZ status: NORMAL, Delayed: False", "op", EpistemicState.OBSERVED),
    )
    r = build_economic_signal(s)

    assert r.operational_delay_observed is False
    demurrage_qs = [q for q in r.economic_questions if "demurrage" in q.question.lower()]
    assert len(demurrage_qs) == 0


# ─── 3. THE FUNDAMENTAL LOOP TEST ─────────────────────────────────────────────

def test_questions_change_between_rounds():
    """
    CORE INVARIANT: R1.questions != R2.questions when new evidence resolves
    a precondition. This proves the loop of investigation is real.
    """
    # Round 1 — baseline
    r1 = build_economic_signal(_make_shipment(*_BASE_EVIDENCE))
    q1 = {q.question for q in r1.economic_questions}

    # Round 2 — add destination
    r2 = build_economic_signal(_make_shipment(
        *_BASE_EVIDENCE,
        ("destination_port", "CNQIN", "ais_voyage_history", EpistemicState.OBSERVED),
    ))
    q2 = {q.question for q in r2.economic_questions}

    # They must differ
    assert q1 != q2, "Questions must change when evidence changes state"

    # Destination discovery must be removed
    dest_q_removed = any("destino inland" in q.lower() for q in (q1 - q2))
    assert dest_q_removed, "Destination discovery question must leave R2"

    # Corridor question must be added
    corridor_q_added = any("corredor" in q.lower() for q in (q2 - q1))
    assert corridor_q_added, "Corridor question must enter R2 (destination now known)"

    # Identity must have advanced
    assert r1.identity_status == "provisional_aggregator"
    assert r2.identity_status == "candidate"


# ─── 4. GROUNDED_IN CORRECTNESS ───────────────────────────────────────────────

def test_consignee_question_grounded_in_cargo():
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    consignee_qs = [q for q in r.economic_questions if "consignee" in q.question.lower()]
    assert len(consignee_qs) >= 1
    assert consignee_qs[0].grounded_in == "cargo"


def test_demurrage_question_grounded_in_status():
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    demurrage_qs = [q for q in r.economic_questions if "demurrage" in q.question.lower()]
    assert len(demurrage_qs) >= 1
    assert demurrage_qs[0].grounded_in == "status"


def test_corridor_question_grounded_in_destination():
    s = _make_shipment(
        *_BASE_EVIDENCE,
        ("destination_port", "CNQIN", "ais_voyage_history", EpistemicState.OBSERVED),
    )
    r = build_economic_signal(s)

    corridor_qs = [q for q in r.economic_questions if "corredor" in q.question.lower()]
    assert len(corridor_qs) >= 1
    assert corridor_qs[0].grounded_in == "destination_port"


# ─── 5. WOULD_UNLOCK CORRECTNESS ──────────────────────────────────────────────

def test_would_unlock_only_contains_modeled_unknown_fields():
    """
    would_unlock must NOT contain fields that do not exist in
    ShipmentReconstruction (e.g., ncm_code, volume_kg, importer_license).
    """
    from src.reconstruction.economic_intelligence import _MODELED_FIELDS
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    for ne in r.next_evidence:
        for f in ne.would_unlock:
            assert f in _MODELED_FIELDS, \
                f"would_unlock contains non-modeled field: '{f}' in source '{ne.source}'"


def test_external_fields_are_documented_not_in_would_unlock():
    """
    Fields like ncm_code and importer_license must appear in
    external_fields_not_yet_modeled, not in would_unlock.
    """
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)

    all_unlocked = {f for ne in r.next_evidence for f in ne.would_unlock}
    assert "ncm_code" not in all_unlocked
    assert "importer_license" not in all_unlocked
    assert "volume_kg" not in all_unlocked

    all_external = {f for ne in r.next_evidence for f in ne.external_fields_not_yet_modeled}
    # At least some external fields should be documented
    assert len(all_external) > 0


def test_would_unlock_empty_when_all_modeled_fields_are_known():
    """If all fields that a source could populate are already known, would_unlock is empty."""
    # All standard fields known
    s = _make_shipment(
        ("vessel",           "CL HENGYANG", "src", EpistemicState.OBSERVED),
        ("cargo",            "CLORETO DE POTASSIO (FERTILIZANTE)", "src", EpistemicState.OBSERVED),
        ("port_call",        "BRSSZ", "src", EpistemicState.OBSERVED),
        ("status",           "NORMAL", "src", EpistemicState.OBSERVED),
        ("consignee",        "AGRI_CORP", "bl", EpistemicState.OBSERVED),
        ("shipper",          "POTASH_LTD", "bl", EpistemicState.OBSERVED),
        ("destination_port", "CNQIN", "ais", EpistemicState.OBSERVED),
        ("origin_port",      "NLRTM", "ais", EpistemicState.OBSERVED),
        ("voyage",           "VOY-2026-001", "ais", EpistemicState.OBSERVED),
    )
    r = build_economic_signal(s)

    for ne in r.next_evidence:
        assert ne.would_unlock == [], \
            f"Source '{ne.source}' should not unlock anything when all fields are known"


# ─── 6. SERIALIZATION ─────────────────────────────────────────────────────────

def test_full_report_is_serializable():
    s = _make_shipment(*_BASE_EVIDENCE)
    r = build_economic_signal(s)
    d = r.as_dict()
    j = json.dumps(d, ensure_ascii=False)

    assert len(j) > 100
    assert "known" in d
    assert "unknown" in d
    assert "economic_questions" in d
    assert "next_evidence" in d
    assert d["cargo_commodity_class"]["epistemic_state"] == "derived"
