"""
Investigation Protocol — AETHER-X Knowledge Plane
Ordem 14: Executive Investigation Loop

PURPOSE:
    Implement the investigation cycle:

        EconomicSignalReport
             ↓
        select_question()         — deterministic, one question at a time
             ↓
        attempt_resolution()      — tries registered AETHER-X sources
             ↓
        InvestigationStep         — EVIDENCE_FOUND or EVIDENCE_UNAVAILABLE
             ↓
        new RichEvidence          — added to ShipmentReconstruction
             ↓
        build_economic_signal()   — new report with updated questions

RULES:
    - No new fields are created by inference.
    - EVIDENCE_UNAVAILABLE is a valid, first-class outcome.
    - Only sources registered in _SOURCE_REGISTRY are queried.
    - Registered sources expose exactly what the AETHER-X stack provides today;
      sources not yet integrated (BL, ANTAQ, AIS, customs) are declared absent.
    - Provenance is complete for every resolved evidence.
    - This module is stateless: it does not persist anything.

SOURCE REGISTRY AUDIT (as of Ordem 14):
    ✓ assess_logistics_disruption  → port status, delay, estimated demurrage rate
    ✗ vessel_voyage_history_ais    → not connected (EVIDENCE_UNAVAILABLE)
    ✗ antaq_manifests              → not connected (EVIDENCE_UNAVAILABLE)
    ✗ bill_of_lading               → not connected (EVIDENCE_UNAVAILABLE)
    ✗ customs_data_siscomex        → not connected (EVIDENCE_UNAVAILABLE)
    ✗ mapa_license_database        → not connected (EVIDENCE_UNAVAILABLE)
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.reconstruction.models import (
    EpistemicState, EntityRef, RichEvidence, ShipmentReconstruction
)
from src.reconstruction.economic_intelligence import EconomicQuestion, EconomicSignalReport


# ─── OUTCOME CONSTANTS ────────────────────────────────────────────────────────

EVIDENCE_FOUND       = "EVIDENCE_FOUND"
EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"


# ─── DATA STRUCTURES ──────────────────────────────────────────────────────────

@dataclass
class InvestigationStep:
    """
    Records a single round of the investigation cycle.

    Invariants:
    - If outcome == EVIDENCE_FOUND: evidence_found is not None
    - If outcome == EVIDENCE_UNAVAILABLE: reason_unavailable is not None
    - evidence_found carries complete provenance (source, source_observed_at,
      retrieved_at, epistemic_state)
    - The investigation never invents a value when the source cannot answer.
    """
    selected_question: EconomicQuestion
    target_field: str               # The ShipmentReconstruction field targeted
    candidate_sources: List[str]    # Sources that declare they cover this field
    queried_source: str             # The source actually queried
    outcome: str                    # EVIDENCE_FOUND | EVIDENCE_UNAVAILABLE
    evidence_found: Optional[RichEvidence] = None
    reason_unavailable: Optional[str] = None
    retrieved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class InvestigationRound:
    """
    A complete round: report before, step taken, evidence added (if any),
    report after, and the delta.
    """
    round_number: int
    report_before: EconomicSignalReport
    step: InvestigationStep
    report_after: EconomicSignalReport

    @property
    def questions_removed(self) -> List[str]:
        q_before = {q.question for q in self.report_before.economic_questions}
        q_after  = {q.question for q in self.report_after.economic_questions}
        return sorted(q_before - q_after)

    @property
    def questions_added(self) -> List[str]:
        q_before = {q.question for q in self.report_before.economic_questions}
        q_after  = {q.question for q in self.report_after.economic_questions}
        return sorted(q_after - q_before)

    @property
    def economic_state_changed(self) -> bool:
        return (
            self.questions_removed != [] or
            self.questions_added   != [] or
            self.report_before.identity_status != self.report_after.identity_status
        )

    def provenance_for_changed_fields(self) -> List[Dict[str, Any]]:
        """
        For every field that moved from UNKNOWN to KNOWN between rounds,
        return the complete evidence chain.
        """
        known_before = {k.field for k in self.report_before.known}
        known_after  = {k.field for k in self.report_after.known}
        newly_known  = known_after - known_before

        provenance = []
        if self.step.evidence_found and self.step.target_field in newly_known:
            ev = self.step.evidence_found
            provenance.append({
                "field":           self.step.target_field,
                "previous_state":  "unknown",
                "new_state":       "observed",
                "evidence_id":     ev.evidence_id,
                "source":          ev.source,
                "source_observed_at": ev.source_observed_at,
                "retrieved_at":    ev.retrieved_at,
                "epistemic_state": ev.epistemic_state.value,
            })
        return provenance


# ─── QUESTION SELECTOR ────────────────────────────────────────────────────────

# Maps target_field → candidate sources (from _CARGO_DOMAIN next_evidence)
_FIELD_TO_SOURCES: Dict[str, List[str]] = {
    "consignee":       ["antaq_manifests", "bill_of_lading", "customs_data_siscomex"],
    "shipper":         ["bill_of_lading", "antaq_manifests"],
    "destination_port":["bill_of_lading", "vessel_voyage_history_ais"],
    "origin_port":     ["vessel_voyage_history_ais", "antaq_manifests"],
    "voyage":          ["vessel_voyage_history_ais"],
    "status":          ["assess_logistics_disruption"],
}

# Priority ordering: prefer questions whose grounded_in field is most evidentially rich
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def select_question(report: EconomicSignalReport) -> Optional[EconomicQuestion]:
    """
    Deterministically selects ONE open question to investigate next.

    Selection rule:
    1. Prefer questions with priority="high"
    2. Among equals, prefer questions whose grounded_in field has at least one
       candidate source registered in _FIELD_TO_SOURCES
    3. Among remaining equals, take the first in list order (stable)

    Returns None if there are no active questions.
    """
    active = report.economic_questions
    if not active:
        return None

    def sort_key(q: EconomicQuestion):
        priority_rank = _PRIORITY_ORDER.get(q.priority, 99)
        # Prefer questions with a registered source for their required field
        # (extracted from next_evidence would_unlock)
        has_source = any(
            ne.would_unlock and q.grounded_in in _FIELD_TO_SOURCES
            for ne in report.next_evidence
        )
        source_rank = 0 if has_source else 1
        return (priority_rank, source_rank)

    return sorted(active, key=sort_key)[0]


def _field_for_question(question: EconomicQuestion, report: EconomicSignalReport) -> str:
    """
    Identify the target ShipmentReconstruction field that answering this
    question would populate. Uses grounded_in and the unknown field list.
    """
    # Direct mapping from question's grounded_in to the UNKNOWN field it targets
    # The grounded_in tells us WHAT we know; the unknown field tells us WHAT we need.
    # We infer target by matching question text keywords to unknown fields.
    unknown_fields = {u.field for u in report.unknown}

    keyword_to_field = {
        "consignee":    "consignee",
        "importador":   "consignee",
        "shipper":      "shipper",
        "exportador":   "shipper",
        "destino inland": "destination_port",
        "destino":      "destination_port",
        "corredor":     "destination_port",  # corridor question presupposes dest is known
        "volume":       "voyage",            # volume not modeled; approximate to voyage
        "demurrage":    "status",
        "cambial":      "consignee",         # FX requires consignee
    }

    q_lower = question.question.lower()
    for keyword, target in keyword_to_field.items():
        if keyword in q_lower and target in unknown_fields:
            return target

    # If grounded_in itself is an unknown field, target it directly
    if question.grounded_in in unknown_fields:
        return question.grounded_in

    return "status"  # Fallback: confirm operational status


# ─── SOURCE REGISTRY ──────────────────────────────────────────────────────────
# Each resolver is a callable that takes (port_id, target_field, shipment_id)
# and returns Optional[RichEvidence]. It MUST return None if it cannot answer.

def _resolve_from_assess_logistics(
    port_id: str, target_field: str, shipment_id: str
) -> Optional[RichEvidence]:
    """
    Queries assess_logistics_disruption and extracts evidence for target_field.
    Can populate: status, demurrage exposure signal (as status annotation).
    Cannot populate: consignee, shipper, destination_port, origin_port, voyage.
    """
    from src.api.mcp_app import assess_logistics_disruption
    from src.api.main import get_port_risk

    now = datetime.now(timezone.utc).isoformat()

    if target_field == "status":
        result = assess_logistics_disruption(port_id)
        obs = result.get("observations", [])
        delay_obs = next(
            (o for o in obs if "DELAY" in o.get("fact", "").upper() and "TRUE" in o.get("fact", "").upper()),
            None
        )
        if not delay_obs:
            return None

        return RichEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
            claim_field="status",
            claim_value=delay_obs["fact"],
            entity=EntityRef(type="shipment", raw_name=shipment_id),
            epistemic_state=EpistemicState.OBSERVED,
            confidence=0.85,
            source="assess_logistics_disruption",
            source_observed_at=delay_obs.get("observed_at"),
            retrieved_at=now,
        )

    # This source cannot answer any other field
    return None


_SOURCE_REGISTRY: Dict[str, Any] = {
    "assess_logistics_disruption": _resolve_from_assess_logistics,
    # Sources below are registered but not yet connected → always return UNAVAILABLE
    "vessel_voyage_history_ais":   None,
    "antaq_manifests":             None,
    "bill_of_lading":              None,
    "customs_data_siscomex":       None,
    "mapa_license_database":       None,
}


# ─── INVESTIGATOR ─────────────────────────────────────────────────────────────

def attempt_resolution(
    question: EconomicQuestion,
    report: EconomicSignalReport,
    reconstruction: ShipmentReconstruction,
) -> InvestigationStep:
    """
    Attempts to resolve a selected question against registered AETHER-X sources.

    Returns an InvestigationStep with outcome EVIDENCE_FOUND or EVIDENCE_UNAVAILABLE.
    Never invents data. Never infers from adjacent fields.
    """
    target_field = _field_for_question(question, report)
    candidate_sources = _FIELD_TO_SOURCES.get(target_field, [])
    port_id = reconstruction.port_call.current_value or "UNKNOWN"
    now = datetime.now(timezone.utc).isoformat()

    for source_name in candidate_sources:
        resolver = _SOURCE_REGISTRY.get(source_name)

        if resolver is None:
            # Source is declared but not connected
            continue

        evidence = resolver(port_id, target_field, reconstruction.shipment_id)
        if evidence is not None:
            return InvestigationStep(
                selected_question=question,
                target_field=target_field,
                candidate_sources=candidate_sources,
                queried_source=source_name,
                outcome=EVIDENCE_FOUND,
                evidence_found=evidence,
                retrieved_at=now,
            )

    # No connected source could answer
    tried = [s for s in candidate_sources if _SOURCE_REGISTRY.get(s) is not None]
    not_connected = [s for s in candidate_sources if _SOURCE_REGISTRY.get(s) is None]

    return InvestigationStep(
        selected_question=question,
        target_field=target_field,
        candidate_sources=candidate_sources,
        queried_source=candidate_sources[0] if candidate_sources else "none",
        outcome=EVIDENCE_UNAVAILABLE,
        reason_unavailable=(
            f"No connected source can answer '{target_field}'. "
            f"Tried: {tried or 'none'}. "
            f"Not yet integrated: {not_connected}."
        ),
        retrieved_at=now,
    )
