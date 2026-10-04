"""Fase 2 — superfície de leitura da ShipmentReconstruction (READ SURFACE).

Fonte de verdade: o `evidence_ledger` durável. O snapshot persistido
(`shipment_reconstructions`) é usado apenas como ÍNDICE de escopo/identidade —
nunca como conteúdo. Motivo (Gate 1A, produção 2026-10-03): o boot não repovoa
os dicts em memória do ShadowStore; o primeiro run pós-restart reconstrói o
snapshot só com as evidências novas. Compor a leitura a partir do snapshot
produziria leitura regredida; compor a partir do ledger, não.

Contrato (docs/architecture/reconstruction-persistence-contract.md):
  - Evidence é IMUTÁVEL e o ledger é append-only; retração é tombstone.
  - `urn:shipment:{portcall_id}` é AGREGADOR OPERACIONAL PROVISÓRIO, não
    identidade comercial — a view declara `identity.is_provisional`.
  - O ledger não tem shipment_id: o vínculo evidência↔shipment é por ENTIDADE
    (escopo por porto). A limitação é declarada em `composition.scope_basis`.

Regras epistêmicas da leitura:
  - Nunca fabricar valor: campo sem evidência ativa é UNKNOWN; campo cuja
    evidência foi toda retraída é RETRACTED (valor sempre None).
  - Contradição nunca é mesclada: state=contradiction, value=None e os valores
    conflitantes ficam expostos em `distinct_values`.
  - Multi-fonte do mesmo fato nunca é deduplicada na leitura.
  - Nenhum valor é exposto quando o estado não é publicável.
"""
from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.reconstruction.engine import ReconstructionEngine
from src.reconstruction.models import (
    EpistemicState,
    ShipmentReconstruction,
)

VIEW_SCHEMA = "aetherx.reconstruction.view/v1"
LIST_SCHEMA = "aetherx.reconstruction.list/v1"
READ_MODEL_VERSION = "read_surface_v1"

# Campos canônicos do ShipmentReconstruction (ordem de exibição).
FIELD_ORDER = (
    "vessel", "origin_port", "destination_port", "port_call",
    "voyage", "cargo", "shipper", "consignee", "status",
)

# Campos de escopo usados apenas para resolver QUE entidades-porto delimitam
# o agregado (o snapshot nunca fornece valor/estado).
SCOPE_FIELDS = ("origin_port", "destination_port", "port_call")

# Identificadores de parte: cadeia completa exige chave paga (trial vê apenas
# contagens e estados epistêmicos).
PARTY_FIELDS = ("shipper", "consignee")

# Estados cujo current_value pode ser publicado. Contradição/retração/ausência
# nunca publicam valor como se fosse válido (doutrina ADR-002 do runtime).
PUBLISHABLE_STATES = (
    EpistemicState.OBSERVED,
    EpistemicState.DERIVED,
    EpistemicState.ESTIMATED,
    EpistemicState.INFERRED,
    EpistemicState.HYPOTHESIS,
)


def _default_repository():
    # Singleton atual (testes rebindam ShadowStore._instance); ler via classe,
    # nunca via referência de módulo capturada.
    from src.reconstruction.shadow_store import ShadowStore
    return ShadowStore().repository


def _state_name(state: Any) -> str:
    return state.value if isinstance(state, EpistemicState) else str(state)


def _evidence_entry(ev, role: str) -> Dict[str, Any]:
    return {
        "logical_id": ev.logical_id,
        "evidence_id": ev.evidence_id,
        "role": role,
        "claim_value": ev.claim_value,
        "epistemic_state": _state_name(ev.epistemic_state),
        "confidence": ev.confidence,
        "source": ev.source,
        "source_observed_at": ev.source_observed_at,
        "retrieved_at": ev.retrieved_at,
        "origin_order_id": ev.origin_order_id,
    }


def _resolve_scope(
    snapshot: Optional[ShipmentReconstruction],
    scope_entities: Optional[List[str]],
) -> List[str]:
    if scope_entities:
        return [str(p).strip() for p in scope_entities if str(p).strip()]
    ports: List[str] = []
    if snapshot is not None:
        for name in SCOPE_FIELDS:
            value = getattr(snapshot, name).current_value
            if isinstance(value, str) and value.strip():
                ports.append(value.strip())
    seen, out = set(), []
    for p in ports:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _replay_from_ledger(
    shipment_id: str,
    active: List,
    retracted: List,
) -> ShipmentReconstruction:
    """Replay determinístico do ledger numa reconstrução fresca.

    A evidência retraída NÃO entra no replay: o campo cai naturalmente para o
    que sobra de evidência ativa (ou UNKNOWN), e em seguida é rebaixado para
    RETRACTED quando nada ativo resta para ele.
    """
    fresh = ShipmentReconstruction(shipment_id=shipment_id)
    engine = ReconstructionEngine()
    for ev in active:
        engine.apply_evidence(fresh, ev)

    retracted_by_field: Dict[str, List] = defaultdict(list)
    for ev in retracted:
        retracted_by_field[ev.claim_field].append(ev)

    active_fields_by_name: Dict[str, List] = defaultdict(list)
    for ev in active:
        active_fields_by_name[ev.claim_field].append(ev)

    for field_name, evs in retracted_by_field.items():
        field = getattr(fresh, field_name, None)
        if field is None:
            continue
        field.retracted_evidence_ids = [ev.logical_id for ev in evs]
        if not active_fields_by_name.get(field_name):
            field.state = EpistemicState.RETRACTED
            field.current_value = None
    return fresh


def _field_view(fresh: ShipmentReconstruction, name: str, active, retracted) -> Dict[str, Any]:
    sf = getattr(fresh, name)
    state = _state_name(sf.state)
    publishable = sf.state in PUBLISHABLE_STATES

    chain: List[Dict[str, Any]] = []
    for ev in active:
        if ev.logical_id in sf.supporting_evidence_ids:
            role = "supporting"
        elif ev.logical_id in sf.conflicting_evidence_ids:
            role = "conflicting"
        elif publishable and ev.claim_value == sf.current_value:
            # Evidência ativa do mesmo fato que o replay superou/reordenou —
            # permanece exposta (multi-fonte nunca é deduplicada na leitura).
            role = "corroborating"
        else:
            role = "superseded"
        chain.append(_evidence_entry(ev, role))
    for ev in retracted:
        chain.append(_evidence_entry(ev, "retracted"))

    distinct = sorted(
        {ev.claim_value for ev in active if ev.claim_value is not None},
        key=lambda v: str(v),
    )
    value_sources = (
        {ev.source for ev in active if publishable and ev.claim_value == sf.current_value}
        if publishable else set()
    )

    return {
        "value": sf.current_value if publishable else None,
        "epistemic_state": state,
        "multi_source": len(value_sources) > 1,
        "evidence_chain": chain,
        "active_evidence_count": len(active),
        "retracted_evidence_count": len(retracted),
        **({"distinct_values": distinct} if len(distinct) > 1 else {}),
    }


def _hypotheses_view(
    snapshot: Optional[ShipmentReconstruction],
    active_lids: set,
    retracted_lids: set,
) -> List[Dict[str, Any]]:
    """Hipóteses do snapshot durável, qualificadas contra o ledger atual.

    Hipótese é artefato derivado (nunca evidência primária); a leitura nunca a
    promove, apenas reporta se o suporte dela segue ativo após eventuais
    retrações.
    """
    if snapshot is None:
        return []
    out = []
    for h in snapshot.hypotheses.values():
        active_support = [lid for lid in h.supporting_evidence_ids if lid in active_lids]
        retracted_support = [lid for lid in h.supporting_evidence_ids if lid in retracted_lids]
        out.append({
            "hypothesis_id": h.hypothesis_id,
            "claim_field": h.claim_field,
            "claim_value": h.claim_value,
            "epistemic_state": _state_name(h.epistemic_state),
            "rationale": h.rationale,
            "confidence": h.confidence,
            "created_at": h.created_at,
            "origin": "durable_snapshot",
            "supporting_evidence_ids": h.supporting_evidence_ids,
            "conflicting_evidence_ids": h.conflicting_evidence_ids,
            "supporting_active_count": len(active_support),
            "retracted": bool(h.supporting_evidence_ids)
            and not active_support
            and len(retracted_support) == len(h.supporting_evidence_ids),
        })
    return out


def _economic_layers(fresh: ShipmentReconstruction, include_value: bool):
    signal: Dict[str, Any]
    try:
        from src.reconstruction.economic_intelligence import build_economic_signal
        signal = build_economic_signal(fresh).as_dict()
    except Exception as exc:
        signal = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}

    value: Optional[Dict[str, Any]] = None
    if include_value:
        try:
            from src.reconstruction.economic_value import assess_economic_value
            value = assess_economic_value(fresh).as_dict()
        except Exception as exc:
            value = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    return signal, value


def build_reconstruction_view(
    stable_id: str,
    *,
    repository=None,
    include_economic_value: bool = True,
    scope_entities: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compõe a reconstrução ativa de um shipment EXCLUSIVAMENTE do ledger.

    O snapshot durável é consultado apenas como índice (identity + escopo +
    hipóteses). Nenhum dict em memória do ShadowStore é consultado.
    """
    repo = repository or _default_repository()
    stable_id = str(stable_id).strip()

    if not stable_id.startswith("urn:shipment:"):
        stable_id = f"urn:shipment:{stable_id}"

    snapshot = repo.load_shipment(stable_id)
    if snapshot is None:
        return {
            "schema": VIEW_SCHEMA,
            "found": False,
            "stable_id": stable_id,
            "reason": "no_durable_snapshot",
        }

    shipment_id = snapshot.shipment_id
    scope = _resolve_scope(snapshot, scope_entities)
    scope_basis = "explicit_entities" if scope_entities else (
        "durable_snapshot_fields" if scope else "unresolved"
    )

    active, retracted = [], []
    for port in scope:
        active.extend(repo.get_active_evidence_for_entity(port))
        retracted.extend(repo.get_retracted_evidence_for_entity(port))

    fresh = _replay_from_ledger(shipment_id, active, retracted)

    active_by_field: Dict[str, List] = defaultdict(list)
    for ev in active:
        active_by_field[ev.claim_field].append(ev)
    retracted_by_field: Dict[str, List] = defaultdict(list)
    for ev in retracted:
        retracted_by_field[ev.claim_field].append(ev)

    fields: Dict[str, Dict[str, Any]] = {}
    for name in FIELD_ORDER:
        fields[name] = _field_view(
            fresh, name,
            active_by_field.get(name, []),
            retracted_by_field.get(name, []),
        )

    modeled = set(FIELD_ORDER)
    unmodeled: Dict[str, List[Dict[str, Any]]] = {}
    for claim_field in sorted(set(active_by_field) | set(retracted_by_field)):
        if claim_field in modeled:
            continue
        entries = [
            _evidence_entry(ev, "retracted" if ev in retracted_by_field[claim_field] else "supporting")
            for ev in active_by_field.get(claim_field, []) + retracted_by_field.get(claim_field, [])
        ]
        unmodeled[claim_field] = entries

    field_distribution: Dict[str, int] = defaultdict(int)
    for f in fields.values():
        field_distribution[f["epistemic_state"]] += 1
    active_distribution: Dict[str, int] = defaultdict(int)
    for ev in active:
        active_distribution[_state_name(ev.epistemic_state)] += 1

    signal, value = _economic_layers(fresh, include_economic_value)
    identity_status = signal.get("identity_status") if isinstance(signal, dict) else None

    active_lids = {ev.logical_id for ev in active}
    retracted_lids = {ev.logical_id for ev in retracted}

    return {
        "schema": VIEW_SCHEMA,
        "found": True,
        "stable_id": stable_id,
        "shipment_id": shipment_id,
        "identity": {
            "status": identity_status,
            "is_provisional": identity_status != "identified",
            "note": (
                "`urn:shipment:{portcall_id}` é AGREGADOR OPERACIONAL PROVISÓRIO "
                "(contrato de persistência §2): identifica o gatilho operacional, "
                "não a carga comercial. 1 PortCall -> N Shipments. A transição para "
                "identidade comercial exige evidência semântica (consignee/carga), "
                "nunca o identificador operacional."
            ),
        },
        "composition": {
            "source": "evidence_ledger",
            "ledger_only": True,
            "read_model_version": READ_MODEL_VERSION,
            "scope_entities": scope,
            "scope_basis": scope_basis,
            "scope_limitation": (
                "O ledger é escopado por ENTIDADE (porto), não por shipment: "
                "evidências do mesmo porto pertencem a este agregador enquanto a "
                "identidade semântica do shipment não existir."
            ),
            "durable_snapshot_used_for": ["identity", "scope", "hypotheses"],
            "memory_dicts_consulted": False,
            "active_evidence": len(active),
            "retracted_evidence": len(retracted),
        },
        "fields": fields,
        "unmodeled_claims": unmodeled,
        "epistemic_distribution": {
            "fields": dict(field_distribution),
            "active_evidence": dict(active_distribution),
            "retracted_evidence": len(retracted),
        },
        "contradictions": [
            name for name, f in fields.items() if f["epistemic_state"] == "contradiction"
        ],
        "hypotheses": _hypotheses_view(snapshot, active_lids, retracted_lids),
        "economic_signal": signal,
        "economic_value": value,
        "not_probability": True,
        # Qualificação da PRÓPRIA leitura (doutrina da camada): a projeção de
        # entidade e o teto de estado dos sinais derivados são declarados, nunca
        # apresentados como fato observado.
        "stable_id_is_operational": True,
        "read_limitations": [
            {
                "field": "port_call",
                "epistemic_state": "derived",
                "limitation": (
                    "O port_call do agregado é derivado do escopo do snapshot "
                    "durável (índice de escopo), não de evidência primária de "
                    "chegada do navio."
                ),
            },
            {
                "field": "economic_signal",
                "epistemic_state": "derived",
                "limitation": (
                    "Composto por regras determinísticas sobre os campos da "
                    "reconstrução; nunca excede DERIVED."
                ),
            },
            {
                "field": "economic_value",
                "epistemic_state": "estimated",
                "limitation": (
                    "Estimativas paramétricas (nunca OBSERVED); "
                    "`not_probability` se aplica a toda a superfície."
                ),
            },
        ],
    }


def list_active_reconstructions(
    port_id: Optional[str] = None,
    *,
    repository=None,
) -> Dict[str, Any]:
    """Lista os agregadores duráveis com resumo composto do ledger."""
    repo = repository or _default_repository()
    wanted = port_id.strip().upper() if port_id else None
    items: List[Dict[str, Any]] = []
    for row_stable_id, port_call_id in repo.list_shipments():
        view = build_reconstruction_view(
            row_stable_id, repository=repo, include_economic_value=False
        )
        if not view.get("found"):
            continue
        scope = view["composition"]["scope_entities"]
        if wanted and wanted not in [p.upper() for p in scope]:
            continue
        items.append({
            "stable_id": view["stable_id"],
            "shipment_id": view["shipment_id"],
            "durable_port_call_id": port_call_id,
            "scope_entities": scope,
            "identity_status": view["identity"]["status"],
            "is_provisional": view["identity"]["is_provisional"],
            "fields": {
                name: f["epistemic_state"] for name, f in view["fields"].items()
            },
            "fields_known": [
                name for name, f in view["fields"].items()
                if f["epistemic_state"] in tuple(s.value for s in PUBLISHABLE_STATES)
            ],
            "has_contradiction": bool(view["contradictions"]),
            "active_evidence": view["composition"]["active_evidence"],
            "retracted_evidence": view["composition"]["retracted_evidence"],
        })
    return {
        "schema": LIST_SCHEMA,
        "port_id": wanted,
        "count": len(items),
        "reconstructions": items,
        "composition": {
            "source": "evidence_ledger",
            "ledger_only": True,
            "read_model_version": READ_MODEL_VERSION,
        },
        "not_probability": True,
    }


def redact_view_for_trial(view: Dict[str, Any]) -> Dict[str, Any]:
    """Redação para trial (MCP): identificadores de parte nunca saem de graça.

    Mantém contagens e estados epistêmicos; remove valor e fonte das partes
    (shipper/consignee). O restante da cadeia permanece auditável.
    """
    redacted = copy.deepcopy(view)
    for name in PARTY_FIELDS:
        field = (redacted.get("fields") or {}).get(name)
        if not field:
            continue
        field["value"] = None
        field["redacted"] = True
        for entry in field.get("evidence_chain", []):
            entry["claim_value"] = None
            entry["source"] = None
            entry["evidence_id"] = None
    redacted["redaction"] = {
        "applied": True,
        "plan": "trial",
        "rule": (
            "Identificação de parte (shipper/consignee) exige chave paga: a "
            "cadeia desses campos sai sem valor/fonte, preservando contagens e "
            "estados epistêmicos."
        ),
    }
    _redact_economic_layers(redacted)
    return redacted


def _redact_economic_layers(view: Dict[str, Any]) -> None:
    """Limpa identificação de parte dentro das camadas econômicas.

    Só o VALOR de parte é removido. `caveats` e `requires_for_higher_certainty`
    são preservados: dizem o que falta, não o que foi encontrado.
    """
    signal = view.get("economic_signal")
    if isinstance(signal, dict):
        signal["known"] = [
            ({"field": k.get("field"), "epistemic_state": k.get("epistemic_state"),
              "confidence": k.get("confidence"), "evidence_count": k.get("evidence_count"),
              "value": None}
             if k.get("field") in PARTY_FIELDS else k)
            for k in signal.get("known", [])
        ]

    value = view.get("economic_value")
    if isinstance(value, dict):
        value["observable_facts"] = [
            ({"field": f.get("field"), "epistemic_state": f.get("epistemic_state"),
              "source_label": f.get("source_label"), "observed_at": f.get("observed_at"),
              "value": None}
             if f.get("field") in PARTY_FIELDS else f)
            for f in value.get("observable_facts", [])
        ]
        for impact in value.get("calculable_impacts", []) or []:
            _ = impact  # caveats preservados: declaram ausência, não identificam partes
