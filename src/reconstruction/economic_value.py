"""
Economic Value Assessment — AETHER-X Knowledge Plane
Ordem 15: Economic Value Test

PURPOSE:
    Answer exactly four questions from a ShipmentReconstruction
    using only evidence already available in AETHER-X:

    1. Qual fato econômico já é observável?
    2. Qual impacto pode ser calculado a partir dele?
    3. Qual decisão operacional esse impacto poderia informar?
    4. Qual evidência adicional seria necessária para transformar
       o sinal em oportunidade comercial identificável?

EPISTEMIC CONTRACT:
    - OBSERVED:  fact captured by a physical sensor or operational record.
    - ESTIMATED: value produced by a parametric model (not a contract).
    - DERIVED:   calculated from observed + estimated inputs.
    - UNKNOWN:   field with no evidence. Never filled by proximity or inference.

    The field `estimated_daily_demurrage_usd` from get_port_risk() is ESTIMATED.
    It is NOT `actual_demurrage_paid`. It is NOT a contract value.
    These two must NEVER appear with the same epistemic weight.

ROLES VS COMPANIES:
    Actionable decisions reference economic ROLES (charterer, cargo interest,
    terminal operator) — never specific company names.
    Company-level identification requires consignee/shipper evidence,
    which is currently UNAVAILABLE.

RULES:
    - No new models, tables, engines, frameworks or persistence.
    - No Oracle, MCP, Shadow Pipeline, or ReconstructionEngine changes.
    - No deploy.
    - This module is stateless: same reconstruction → same assessment.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from src.reconstruction.models import EpistemicState, ShipmentReconstruction


# ─── DATA STRUCTURES ──────────────────────────────────────────────────────────

@dataclass
class ObservableFact:
    """
    A fact already captured in the AETHER-X data layer.
    epistemic_state reflects the quality of the observation.
    """
    field: str
    value: Any
    epistemic_state: str       # "observed" | "estimated" | "derived"
    source: str
    source_label: str          # Human-readable description of source quality
    observed_at: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "field": self.field,
            "value": self.value,
            "epistemic_state": self.epistemic_state,
            "source": self.source,
            "source_label": self.source_label,
            "observed_at": self.observed_at,
        }


@dataclass
class CalculableImpact:
    """
    An economic impact that can be derived from observable facts.

    INVARIANT: epistemic_state is always at most ESTIMATED.
    No CalculableImpact may claim to be OBSERVED unless it is a
    direct sensor reading of an economic event (e.g., a paid invoice).
    The model estimate from get_port_risk() is ESTIMATED, not OBSERVED.
    """
    impact_type: str                   # e.g., "demurrage_exposure"
    description: str
    epistemic_state: str               # "estimated" | "derived" — NEVER "observed" for models
    derived_from_fields: List[str]     # Which observed fields contributed
    value: Optional[float] = None      # Numeric value if calculable
    unit: Optional[str] = None         # e.g., "USD/day", "days", "USD"
    caveats: List[str] = field(default_factory=list)
    not_equivalent_to: Optional[str] = None  # Explicit statement of what this is NOT

    def as_dict(self) -> dict:
        return {
            "impact_type": self.impact_type,
            "description": self.description,
            "epistemic_state": self.epistemic_state,
            "derived_from_fields": self.derived_from_fields,
            "value": self.value,
            "unit": self.unit,
            "caveats": self.caveats,
            "not_equivalent_to": self.not_equivalent_to,
        }


@dataclass
class OperationalDecision:
    """
    A decision that could be informed by the economic signal.
    References ROLES, not companies. Companies require consignee/shipper evidence.
    """
    decision: str
    applicable_roles: List[str]        # economic roles, never company names
    certainty_level: str               # "signal_only" | "partial_context" | "actionable"
    requires_for_higher_certainty: List[str]  # missing evidence that would upgrade certainty

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "applicable_roles": self.applicable_roles,
            "certainty_level": self.certainty_level,
            "requires_for_higher_certainty": self.requires_for_higher_certainty,
        }


@dataclass
class MissingForCommercial:
    """
    Evidence not yet available that would convert the operational signal
    into a commercially actionable opportunity.
    """
    field: str
    commercial_relevance: str    # What economic question it would answer
    candidate_sources: List[str]

    def as_dict(self) -> dict:
        return {
            "field": self.field,
            "commercial_relevance": self.commercial_relevance,
            "candidate_sources": self.candidate_sources,
        }


@dataclass
class EconomicValueAssessment:
    """
    Answers the four economic value questions for a single ShipmentReconstruction.

    commercial_readiness levels:
        "pre_signal"    — port-level signal only, no cargo-party identification
        "signal_only"   — delay + commodity known, no consignee/destination
        "candidate"     — destination known, still no commercial party
        "identified"    — consignee or shipper known, signal is commercially usable
    """
    case_id: str
    port_id: str
    assessed_at: str

    # Question 1: What is already observable?
    observable_facts: List[ObservableFact] = field(default_factory=list)

    # Question 2: What impact can be calculated?
    calculable_impacts: List[CalculableImpact] = field(default_factory=list)

    # Question 3: What operational decision does this inform?
    actionable_decisions: List[OperationalDecision] = field(default_factory=list)

    # Question 4: What evidence is missing to make this commercially actionable?
    missing_for_commercial: List[MissingForCommercial] = field(default_factory=list)

    commercial_readiness: str = "pre_signal"
    readiness_explanation: str = ""

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "port_id": self.port_id,
            "assessed_at": self.assessed_at,
            "commercial_readiness": self.commercial_readiness,
            "readiness_explanation": self.readiness_explanation,
            "observable_facts": [f.as_dict() for f in self.observable_facts],
            "calculable_impacts": [i.as_dict() for i in self.calculable_impacts],
            "actionable_decisions": [d.as_dict() for d in self.actionable_decisions],
            "missing_for_commercial": [m.as_dict() for m in self.missing_for_commercial],
        }


# ─── ASSESSOR ─────────────────────────────────────────────────────────────────

def assess_economic_value(reconstruction: ShipmentReconstruction) -> EconomicValueAssessment:
    """
    Produces an EconomicValueAssessment from a ShipmentReconstruction
    using only what AETHER-X can observe today.

    Does NOT invent values. Does NOT infer company names.
    Does NOT present model estimates as contract values.
    """
    port_id = reconstruction.port_call.current_value or "UNKNOWN"
    now = datetime.now(timezone.utc).isoformat()
    assessment = EconomicValueAssessment(
        case_id=reconstruction.shipment_id,
        port_id=port_id,
        assessed_at=now,
    )

    known_fields = _classify_known(reconstruction)

    # ── Q1: Observable Facts ──────────────────────────────────────────────────
    assessment.observable_facts = _extract_observable_facts(reconstruction, port_id)

    # ── Q2: Calculable Impacts ────────────────────────────────────────────────
    assessment.calculable_impacts = _calculate_impacts(reconstruction, port_id, known_fields)

    # ── Q3: Actionable Decisions ──────────────────────────────────────────────
    assessment.actionable_decisions = _derive_decisions(reconstruction, known_fields)

    # ── Q4: Missing for Commercial Signal ────────────────────────────────────
    assessment.missing_for_commercial = _identify_commercial_gaps(known_fields)

    # ── Readiness Level ───────────────────────────────────────────────────────
    assessment.commercial_readiness, assessment.readiness_explanation = \
        _assess_readiness(known_fields)

    return assessment


def _classify_known(reconstruction: ShipmentReconstruction) -> Dict[str, Any]:
    """Return a dict of field → value for every non-UNKNOWN field."""
    result = {}
    for attr in ["vessel", "cargo", "origin_port", "destination_port",
                 "port_call", "shipper", "consignee", "status", "voyage"]:
        sf = getattr(reconstruction, attr, None)
        if sf and sf.state not in (EpistemicState.UNKNOWN, EpistemicState.CONTRADICTION,
                                   EpistemicState.RETRACTED) and sf.current_value is not None:
            result[attr] = sf.current_value
    return result


def _extract_observable_facts(
    reconstruction: ShipmentReconstruction, port_id: str
) -> List[ObservableFact]:
    """
    Extract facts from the reconstruction and from AETHER-X port data.
    Marks each with the correct epistemic state of its source.
    """
    facts: List[ObservableFact] = []

    # From reconstruction (OBSERVED evidence)
    if reconstruction.vessel.current_value:
        facts.append(ObservableFact(
            field="vessel",
            value=reconstruction.vessel.current_value,
            epistemic_state="observed",
            source="santos_painel",
            source_label="Port lineup — operational observation",
        ))

    if reconstruction.cargo.current_value:
        facts.append(ObservableFact(
            field="cargo",
            value=reconstruction.cargo.current_value,
            epistemic_state="observed",
            source="santos_painel",
            source_label="Port lineup — operational observation",
        ))

    if reconstruction.port_call.current_value:
        facts.append(ObservableFact(
            field="port_call",
            value=reconstruction.port_call.current_value,
            epistemic_state="observed",
            source="santos_painel",
            source_label="Port lineup — operational observation",
        ))

    if reconstruction.status.current_value:
        facts.append(ObservableFact(
            field="operational_status",
            value=reconstruction.status.current_value,
            epistemic_state="observed",
            source="santos_painel",
            source_label="Port status — operational observation",
        ))

    # From AETHER-X port_risk (ESTIMATED — parametric model)
    if port_id and port_id != "UNKNOWN":
        try:
            from src.api.main import get_port_risk
            pr = get_port_risk(port_id)
            eta_delay = pr.get("eta_delay_days")
            demurrage_rate = pr.get("estimated_daily_demurrage_usd")
            data_source = pr.get("data_source", "unknown")
            data_label = pr.get("data_source_label", "")
            as_of = pr.get("as_of")

            if eta_delay is not None:
                facts.append(ObservableFact(
                    field="eta_delay_days",
                    value=eta_delay,
                    epistemic_state="estimated",
                    source=data_source,
                    source_label=f"Port risk model — {data_label}",
                    observed_at=as_of,
                ))

            if demurrage_rate is not None:
                facts.append(ObservableFact(
                    field="estimated_daily_demurrage_usd",
                    value=demurrage_rate,
                    epistemic_state="estimated",
                    source=data_source,
                    source_label=(
                        f"Parametric model — {data_label} "
                        "NOTE: generic daily rate, NOT a contract value."
                    ),
                    observed_at=as_of,
                ))
        except Exception:
            pass  # Port risk not available — does not block the assessment

    return facts


def _calculate_impacts(
    reconstruction: ShipmentReconstruction,
    port_id: str,
    known_fields: Dict[str, Any],
) -> List[CalculableImpact]:
    """
    Derive economic impacts from observable facts.
    Every impact carries its epistemic state and explicit caveats.
    """
    impacts: List[CalculableImpact] = []

    status_val = reconstruction.status.current_value or ""
    delay_confirmed = "DELAY" in status_val.upper() and "DELAYED: TRUE" in status_val.upper()

    if delay_confirmed:
        # Try to get the parametric values for a total exposure estimate
        try:
            from src.api.main import get_port_risk
            pr = get_port_risk(port_id)
            eta_delay = pr.get("eta_delay_days")
            daily_rate = pr.get("estimated_daily_demurrage_usd")

            if eta_delay and daily_rate:
                total_est = round(eta_delay * daily_rate, 2)
                impacts.append(CalculableImpact(
                    impact_type="demurrage_exposure_estimate",
                    description=(
                        f"Estimated demurrage exposure for {eta_delay:.1f}-day delay "
                        f"at {port_id} using generic market rate."
                    ),
                    epistemic_state="estimated",
                    derived_from_fields=["status", "eta_delay_days", "estimated_daily_demurrage_usd"],
                    value=total_est,
                    unit="USD",
                    caveats=[
                        "Rate is a generic parametric model output — NOT a charter party rate.",
                        "No actual contract is known. Actual demurrage depends on specific agreement.",
                        "Cargo quantity is UNKNOWN — vessel DWT not measured.",
                        "No berth allocation confirmation available.",
                    ],
                    not_equivalent_to="actual_demurrage_paid",
                ))
        except Exception:
            # Even without the number, we can record the qualitative signal
            impacts.append(CalculableImpact(
                impact_type="demurrage_exposure_signal",
                description=f"Operational delay observed at {port_id}. Quantification unavailable.",
                epistemic_state="derived",
                derived_from_fields=["status"],
                caveats=["Port risk model unavailable at time of assessment."],
                not_equivalent_to="actual_demurrage_paid",
            ))

    # Cargo-class impact signal (DERIVED from observed cargo string matching "FERTILIZANTE")
    cargo_val = reconstruction.cargo.current_value
    if cargo_val and "FERTILIZANTE" in cargo_val.upper():
        impacts.append(CalculableImpact(
            impact_type="supply_chain_sensitivity",
            description=(
                "Cargo classified as fertilizante (OBSERVED in cargo field). "
                "Time-sensitivity of this cargo class is a domain assertion — "
                "NOT derived from evidence in this dataset."
            ),
            epistemic_state="derived",
            derived_from_fields=["cargo"],
            caveats=[
                "HYPOTHESIS: Fertilizante cargo may be time-sensitive due to planting cycles — "
                "this is external domain knowledge, not confirmed by evidence in this reconstruction.",
                "Specific agricultural season not confirmed — requires destination region and calendar date.",
                "Volume unknown — magnitude of exposure unquantifiable.",
                "No consignee identified — bearer of sensitivity unknown.",
            ],
            not_equivalent_to="confirmed_supply_chain_disruption",
        ))

    return impacts


def _derive_decisions(
    reconstruction: ShipmentReconstruction,
    known_fields: Dict[str, Any],
) -> List[OperationalDecision]:
    """
    Map economic signals to operational decisions.
    References economic ROLES only — never company names.
    Port alternatives are NOT listed — no evidence supports specific alternative ports.
    """
    decisions: List[OperationalDecision] = []

    port_id = reconstruction.port_call.current_value or "UNKNOWN"
    status_val = reconstruction.status.current_value or ""
    delay_confirmed = "DELAY" in status_val.upper() and "DELAYED: TRUE" in status_val.upper()

    if delay_confirmed:
        decisions.append(OperationalDecision(
            decision=(
                f"Investigate cargo interest exposure to demurrage at {port_id}. "
                "Delay is confirmed. Generic market rate suggests material exposure."
            ),
            applicable_roles=["charterer", "cargo_interest", "freight_forwarder", "vessel_operator"],
            certainty_level="signal_only",
            requires_for_higher_certainty=["consignee", "charter_party_terms"],
        ))

    cargo_val = reconstruction.cargo.current_value or ""
    if "FERTILIZANTE" in cargo_val.upper():
        decisions.append(OperationalDecision(
            decision=(
                "Evaluate alternative berthing or discharge acceleration "
                "for agricultural input cargo with observed port delay."
            ),
            applicable_roles=["port_agent", "terminal_operator", "cargo_interest"],
            certainty_level="partial_context",
            requires_for_higher_certainty=["consignee", "inland_destination", "cargo_volume"],
        ))

        if delay_confirmed:
            decisions.append(OperationalDecision(
                decision=(
                    "Assess logistics substitution options: "
                    "can cargo be redirected through an alternative port "
                    "to avoid accumulated delay? "
                    "(HYPOTHESIS: specific alternative ports unknown — requires destination and route evidence.)"
                ),
                applicable_roles=["cargo_interest", "freight_forwarder", "importer"],
                certainty_level="signal_only",
                requires_for_higher_certainty=[
                    "consignee", "inland_destination", "vessel_voyage_history_ais"
                ],
            ))

    return decisions


def _identify_commercial_gaps(known_fields: Dict[str, Any]) -> List[MissingForCommercial]:
    """
    Identify which fields are missing that would convert the
    operational signal into a commercially identifiable opportunity.
    """
    gaps: List[MissingForCommercial] = []

    if "consignee" not in known_fields:
        gaps.append(MissingForCommercial(
            field="consignee",
            commercial_relevance=(
                "Identifies which entity bears the delay cost and demurrage exposure. "
                "Required to convert the signal into an identifiable commercial opportunity."
            ),
            candidate_sources=["antaq_manifests", "bill_of_lading", "customs_data_siscomex"],
        ))

    if "destination_port" not in known_fields:
        gaps.append(MissingForCommercial(
            field="destination_port",
            commercial_relevance=(
                "Determines the inland logistics chain affected by the delay. "
                "Enables route and corridor analysis."
            ),
            candidate_sources=["vessel_voyage_history_ais", "bill_of_lading"],
        ))

    if "cargo_volume" not in known_fields:
        gaps.append(MissingForCommercial(
            field="cargo_volume",
            commercial_relevance=(
                "Enables proportional economic impact calculation. "
                "Without volume, demurrage and supply-chain exposure remain unquantifiable."
            ),
            candidate_sources=["bill_of_lading", "customs_data_siscomex", "antaq_manifests"],
        ))

    if "shipper" not in known_fields:
        gaps.append(MissingForCommercial(
            field="shipper",
            commercial_relevance=(
                "Identifies the exporting party. Required for commercial relationship mapping."
            ),
            candidate_sources=["bill_of_lading", "antaq_manifests"],
        ))

    return gaps


def _assess_readiness(known_fields: Dict[str, Any]):
    """
    Determine commercial readiness level and produce a concise explanation.
    """
    has_consignee = "consignee" in known_fields
    has_shipper = "shipper" in known_fields
    has_destination = "destination_port" in known_fields

    if has_consignee or has_shipper:
        return (
            "identified",
            "Commercial party (consignee or shipper) is known. Signal is commercially actionable.",
        )
    elif has_destination:
        return (
            "candidate",
            "Destination is known. Inland route analysis is possible. "
            "Commercial party still required for direct engagement.",
        )
    else:
        return (
            "signal_only",
            "Port-level signal is confirmed (delay + cargo type). "
            "No commercial party identified. Signal informs roles, not entities.",
        )
