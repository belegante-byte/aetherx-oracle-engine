"""
Economic Intelligence Layer — AETHER-X Knowledge Plane
Version: 13.1 — Corrected epistemic contract

CORRECTIONS FROM AUDIT (Ordem 13.1):
  1. commodity_class is now a ClassifiedField with state=DERIVED, derived_from=cargo.
     It was previously a plain string, indistinguishable from an OBSERVED fact.
  2. economic_questions now use explicit QuestionTemplate preconditions.
     Each question declares: which fields must be KNOWN for the question to be meaningful,
     and which fields must be UNKNOWN for the question to still be open.
     The former global HIGH rule (binary over any unknown field) is removed.
  3. grounded_in is now the specific OBSERVED field that makes each question arise,
     not the generic category "cargo".
  4. would_unlock now only declares fields that (a) exist in ShipmentReconstruction
     and (b) are currently UNKNOWN. Fields external to the model are documented
     as external_fields_not_yet_modeled and do NOT appear in would_unlock.
"""

from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from src.reconstruction.models import ShipmentReconstruction, EpistemicState


# ─── MONITORED FIELDS ─────────────────────────────────────────────────────────
# The canonical set of fields that exist in ShipmentReconstruction.
# would_unlock may only reference names from this set.
_MODELED_FIELDS: Set[str] = {
    "vessel", "cargo", "origin_port", "destination_port",
    "port_call", "shipper", "consignee", "status", "voyage",
}

_FIELDS_MONITORED = [
    ("vessel",           "vessel name or IMO"),
    ("cargo",            "cargo type or commodity"),
    ("origin_port",      "port of origin or loading"),
    ("destination_port", "destination port"),
    ("port_call",        "port call event"),
    ("shipper",          "shipper / exporter entity"),
    ("consignee",        "consignee / importer entity"),
    ("status",           "operational status at port"),
    ("voyage",           "voyage reference"),
]


# ─── QUESTION TEMPLATES ────────────────────────────────────────────────────────
@dataclass
class QuestionTemplate:
    """
    A question is active ONLY when ALL of its preconditions are satisfied:

    - requires_known:   fields that must be OBSERVED/DERIVED/ESTIMATED (not UNKNOWN)
                        for this question to be meaningful. The question presupposes
                        these facts exist.
    - requires_unknown: fields that must be UNKNOWN for this question to be OPEN.
                        If the field is already known, the question is resolved and
                        must not appear.
    - grounded_in:      the specific known field whose value raises this question.
    - priority:         economic urgency WHEN the question is active.
    """
    question: str
    requires_known: List[str]
    requires_unknown: List[str]
    grounded_in: str
    priority: str  # "high" | "medium" | "low"


# ─── CARGO DOMAIN ─────────────────────────────────────────────────────────────
# Maps cargo values to domain knowledge.
# Questions are templates with explicit preconditions — NOT static strings.
# next_evidence declares which model fields a source would populate,
# plus external fields not yet in the model.

_CARGO_DOMAIN: Dict[str, Dict[str, Any]] = {
    "CLORETO DE POTASSIO (FERTILIZANTE)": {
        "commodity_class": "agricultural_input",
        "sensitivity": "strategic_agricultural_input",
        "questions": [
            QuestionTemplate(
                question="Quem é o importador/consignee? (informação ausente no dataset atual)",
                requires_known=["cargo", "port_call"],
                requires_unknown=["consignee"],
                grounded_in="cargo",
                priority="high",
            ),
            QuestionTemplate(
                question="Qual é o destino inland? (destino ausente no dataset atual)",
                requires_known=["cargo", "port_call"],
                requires_unknown=["destination_port"],
                grounded_in="port_call",
                priority="high",
            ),
            QuestionTemplate(
                question="Qual corredor logístico conecta Santos ao destino inland?",
                # Only meaningful when we know both origin (port_call) and destination
                requires_known=["port_call", "destination_port"],
                requires_unknown=[],
                grounded_in="destination_port",
                priority="medium",
            ),
            QuestionTemplate(
                question="Qual o volume total da carga? (DWT não mensurado — dado ausente)",
                requires_known=["cargo"],
                requires_unknown=["consignee"],  # Without consignee, volume is unactionable
                grounded_in="cargo",
                priority="medium",
            ),
            QuestionTemplate(
                # Exposure requires volume + price, neither modeled yet.
                # Only present as actionable if we at least know consignee (to have a contract).
                question="Existe exposição cambial relevante dado o valor CIF estimado?",
                requires_known=["cargo", "destination_port", "consignee"],
                requires_unknown=[],
                grounded_in="consignee",
                priority="low",
            ),
        ],
        "next_evidence": [
            {
                "source": "antaq_manifests",
                "modeled_fields": ["consignee", "origin_port"],
                "external_fields_not_yet_modeled": ["ncm", "volume_kg", "port_of_loading"],
            },
            {
                "source": "bill_of_lading",
                "modeled_fields": ["shipper", "consignee", "destination_port"],
                "external_fields_not_yet_modeled": ["cargo_weight_kg"],
            },
            {
                "source": "vessel_voyage_history_ais",
                "modeled_fields": ["origin_port", "destination_port", "voyage"],
                "external_fields_not_yet_modeled": ["previous_calls"],
            },
            {
                "source": "customs_data_siscomex",
                "modeled_fields": ["consignee"],
                "external_fields_not_yet_modeled": ["ncm_code", "volume_kg", "importer_license"],
            },
        ],
    },
    "CELULOSE": {
        "commodity_class": "industrial_export",
        "sensitivity": "pulp_export_brazil",
        "questions": [
            QuestionTemplate(
                question="Qual é o exportador/shipper? (informação ausente no dataset atual)",
                requires_known=["cargo", "port_call"],
                requires_unknown=["shipper"],
                grounded_in="cargo",
                priority="high",
            ),
            QuestionTemplate(
                question="Qual é o destino? (destino ausente no dataset atual)",
                requires_known=["cargo"],
                requires_unknown=["destination_port"],
                grounded_in="cargo",
                priority="high",
            ),
            QuestionTemplate(
                question="Existe delay de berço que impacte o custo de overstay?",
                requires_known=["cargo", "status"],
                requires_unknown=[],
                grounded_in="status",
                priority="medium",
            ),
        ],
        "next_evidence": [
            {
                "source": "bill_of_lading",
                "modeled_fields": ["shipper", "consignee", "destination_port"],
                "external_fields_not_yet_modeled": ["cargo_weight_kg"],
            },
            {
                "source": "vessel_voyage_history_ais",
                "modeled_fields": ["destination_port", "voyage"],
                "external_fields_not_yet_modeled": ["next_call"],
            },
        ],
    },
    "CONTEINER": {
        "commodity_class": "general_cargo_container",
        "sensitivity": "heterogeneous",
        "questions": [
            QuestionTemplate(
                question="Qual armador/shipping line opera esta escala?",
                requires_known=["vessel", "port_call"],
                requires_unknown=["shipper"],
                grounded_in="vessel",
                priority="medium",
            ),
        ],
        "next_evidence": [
            {
                "source": "vessel_voyage_history_ais",
                "modeled_fields": ["voyage", "origin_port"],
                "external_fields_not_yet_modeled": ["carrier", "service_name"],
            },
        ],
    },
}

_DEFAULT_QUESTIONS = [
    QuestionTemplate(
        question="Qual é o importador ou exportador desta carga?",
        requires_known=["cargo"],
        requires_unknown=["consignee", "shipper"],
        grounded_in="cargo",
        priority="high",
    ),
    QuestionTemplate(
        question="Qual é o destino final (inland ou porto)?",
        requires_known=["port_call"],
        requires_unknown=["destination_port"],
        grounded_in="port_call",
        priority="high",
    ),
]

_DEFAULT_NEXT_EVIDENCE = [
    {
        "source": "bill_of_lading",
        "modeled_fields": ["shipper", "consignee", "destination_port"],
        "external_fields_not_yet_modeled": [],
    },
    {
        "source": "vessel_voyage_history_ais",
        "modeled_fields": ["origin_port", "destination_port"],
        "external_fields_not_yet_modeled": [],
    },
]


# ─── REPORT MODELS ────────────────────────────────────────────────────────────

@dataclass
class ClassifiedField:
    """
    A field whose value is derived from an observed field via a static taxonomy.
    It is NOT OBSERVED — it is DERIVED.
    """
    value: str
    epistemic_state: str = "derived"
    derived_from: str = ""

    def as_dict(self) -> dict:
        return {
            "value": self.value,
            "epistemic_state": self.epistemic_state,
            "derived_from": self.derived_from,
        }


@dataclass
class KnownField:
    field: str
    value: Any
    epistemic_state: str
    confidence: float
    source_evidence_count: int


@dataclass
class UnknownField:
    field: str
    reason: str


@dataclass
class EconomicQuestion:
    question: str
    grounded_in: str
    priority: str


@dataclass
class NextEvidence:
    source: str
    would_unlock: List[str]               # Only modeled fields currently UNKNOWN
    external_fields_not_yet_modeled: List[str]  # Fields the source carries, not yet in model


@dataclass
class EconomicSignalReport:
    """
    The economic signal produced from a ShipmentReconstruction.

    INVARIANTS:
    - cargo_commodity_class.epistemic_state == "derived" always (never "observed")
    - economic_questions contains only questions whose preconditions are met
    - next_evidence.would_unlock contains only modeled fields that are UNKNOWN
    - The report is stateless: same reconstruction → same report (deterministic)
    """
    shipment_id: str
    shipment_stable_id: str
    identity_status: str
    cargo_commodity_class: ClassifiedField

    known: List[KnownField] = field(default_factory=list)
    unknown: List[UnknownField] = field(default_factory=list)
    economic_questions: List[EconomicQuestion] = field(default_factory=list)
    next_evidence: List[NextEvidence] = field(default_factory=list)

    total_evidence_count: int = 0
    total_hypotheses_count: int = 0
    has_contradiction: bool = False
    operational_delay_observed: bool = False

    def as_dict(self) -> dict:
        return {
            "shipment_id": self.shipment_id,
            "stable_id": self.shipment_stable_id,
            "identity_status": self.identity_status,
            "cargo_commodity_class": self.cargo_commodity_class.as_dict(),
            "known": [
                {
                    "field": k.field,
                    "value": k.value,
                    "epistemic_state": k.epistemic_state,
                    "confidence": k.confidence,
                    "evidence_count": k.source_evidence_count,
                }
                for k in self.known
            ],
            "unknown": [
                {"field": u.field, "reason": u.reason}
                for u in self.unknown
            ],
            "economic_questions": [
                {
                    "question": q.question,
                    "grounded_in": q.grounded_in,
                    "priority": q.priority,
                }
                for q in self.economic_questions
            ],
            "next_evidence": [
                {
                    "source": e.source,
                    "would_unlock": e.would_unlock,
                    "external_fields_not_yet_modeled": e.external_fields_not_yet_modeled,
                }
                for e in self.next_evidence
            ],
            "meta": {
                "total_evidence_count": self.total_evidence_count,
                "total_hypotheses_count": self.total_hypotheses_count,
                "has_contradiction": self.has_contradiction,
                "operational_delay_observed": self.operational_delay_observed,
            }
        }


# ─── ANALYZER ─────────────────────────────────────────────────────────────────

_KNOWN_THRESHOLD = {
    EpistemicState.OBSERVED: 0.95,
    EpistemicState.DERIVED: 0.75,
    EpistemicState.ESTIMATED: 0.60,
    EpistemicState.INFERRED: 0.50,
}


def build_economic_signal(reconstruction: ShipmentReconstruction) -> EconomicSignalReport:
    """
    Reads a ShipmentReconstruction and produces an EconomicSignalReport.

    Does NOT write anywhere. Does NOT infer missing fields. Does NOT promote
    UNKNOWN to any other state without supporting evidence.
    Questions are active ONLY when their explicit preconditions are met.
    """
    known_fields: List[KnownField] = []
    unknown_fields: List[UnknownField] = []
    has_contradiction = False
    operational_delay_observed = False

    # ─── Step 1: Classify each monitored field ────────────────────────────────
    for attr_name, _ in _FIELDS_MONITORED:
        sf = getattr(reconstruction, attr_name, None)
        if sf is None:
            unknown_fields.append(UnknownField(
                field=attr_name, reason="field not present in reconstruction"
            ))
            continue

        state = sf.state
        val = sf.current_value

        if state == EpistemicState.UNKNOWN or val is None:
            unknown_fields.append(UnknownField(
                field=attr_name, reason="no evidence recorded for this field"
            ))
        elif state == EpistemicState.CONTRADICTION:
            has_contradiction = True
            unknown_fields.append(UnknownField(
                field=attr_name,
                reason=f"CONTRADICTION — {len(sf.conflicting_evidence_ids)} conflicting evidences",
            ))
        elif state == EpistemicState.RETRACTED:
            unknown_fields.append(UnknownField(
                field=attr_name, reason="previously observed, now retracted by tombstone"
            ))
        else:
            confidence = _KNOWN_THRESHOLD.get(state, 0.5)
            known_fields.append(KnownField(
                field=attr_name,
                value=val,
                epistemic_state=state.value,
                confidence=confidence,
                source_evidence_count=len(sf.supporting_evidence_ids),
            ))
            if attr_name == "status" and isinstance(val, str):
                val_upper = val.upper()
                # Must contain DELAY *and* explicit confirmation (Delayed: True)
                # Strings like "Delayed: False" must NOT trigger this flag
                if "DELAY" in val_upper and "DELAYED: TRUE" in val_upper:
                    operational_delay_observed = True

    known_names: Set[str] = {k.field for k in known_fields}
    unknown_names: Set[str] = {u.field for u in unknown_fields}

    # ─── Step 2: Cargo domain classification ─────────────────────────────────
    # commodity_class is DERIVED from cargo, never OBSERVED.
    cargo_val = reconstruction.cargo.current_value
    cargo_state = reconstruction.cargo.state
    commodity_class = ClassifiedField(
        value="unknown",
        epistemic_state="derived",
        derived_from="cargo",
    )
    domain_templates: List[QuestionTemplate] = _DEFAULT_QUESTIONS
    domain_next_evidence = _DEFAULT_NEXT_EVIDENCE

    if cargo_state not in (EpistemicState.UNKNOWN, EpistemicState.CONTRADICTION) and cargo_val:
        for k, v in _CARGO_DOMAIN.items():
            if k.upper() == cargo_val.upper() or k.upper() in cargo_val.upper():
                commodity_class = ClassifiedField(
                    value=v["commodity_class"],
                    epistemic_state="derived",
                    derived_from="cargo",
                )
                domain_templates = v["questions"]
                domain_next_evidence = v["next_evidence"]
                break

    # ─── Step 3: Evaluate question preconditions ──────────────────────────────
    # A question is ACTIVE if and only if:
    #   - all requires_known fields are in known_names
    #   - all requires_unknown fields (if any) are in unknown_names
    #     (empty requires_unknown means the question is open regardless)
    economic_questions: List[EconomicQuestion] = []

    for tmpl in domain_templates:
        # Precondition 1: all required known fields must be KNOWN
        known_satisfied = all(f in known_names for f in tmpl.requires_known)
        if not known_satisfied:
            continue

        # Precondition 2: all required unknown fields must still be UNKNOWN
        # (empty list means the question is always relevant when requires_known is met)
        unknown_satisfied = all(f in unknown_names for f in tmpl.requires_unknown)
        if not unknown_satisfied:
            continue

        economic_questions.append(EconomicQuestion(
            question=tmpl.question,
            grounded_in=tmpl.grounded_in,
            priority=tmpl.priority,
        ))

    # Demurrage question: only when operational delay is observed
    if operational_delay_observed:
        economic_questions.append(EconomicQuestion(
            question="Qual é a exposição a demurrage dado o atraso operacional observado e ausência de contrato de frete?",
            grounded_in="status",
            priority="high",
        ))

    # ─── Step 4: Build next_evidence with corrected would_unlock ─────────────
    # would_unlock: only modeled fields that are currently UNKNOWN
    # external_fields_not_yet_modeled: documented separately, not in would_unlock
    next_evidence_list: List[NextEvidence] = []

    for ne in domain_next_evidence:
        modeled = ne.get("modeled_fields", [])
        external = ne.get("external_fields_not_yet_modeled", [])

        # Only unlock fields that (a) exist in the model AND (b) are currently UNKNOWN
        would_unlock = [
            f for f in modeled
            if f in _MODELED_FIELDS and f in unknown_names
        ]

        next_evidence_list.append(NextEvidence(
            source=ne["source"],
            would_unlock=would_unlock,
            external_fields_not_yet_modeled=external,
        ))

    # ─── Step 5: Identity resolution ─────────────────────────────────────────
    has_consignee = "consignee" in known_names
    has_shipper = "shipper" in known_names
    has_destination = "destination_port" in known_names

    if has_consignee or has_shipper:
        identity_status = "identified"
    elif has_destination and cargo_state not in (EpistemicState.UNKNOWN,):
        identity_status = "candidate"
    else:
        identity_status = "provisional_aggregator"

    return EconomicSignalReport(
        shipment_id=reconstruction.shipment_id,
        shipment_stable_id=reconstruction.stable_id,
        identity_status=identity_status,
        cargo_commodity_class=commodity_class,
        known=known_fields,
        unknown=unknown_fields,
        economic_questions=economic_questions,
        next_evidence=next_evidence_list,
        total_evidence_count=len(reconstruction.evidence_store),
        total_hypotheses_count=len(reconstruction.hypotheses),
        has_contradiction=has_contradiction,
        operational_delay_observed=operational_delay_observed,
    )
