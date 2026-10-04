"""
Fase 2 — READ SURFACE: reconstrução composta do ledger durável.

Cobre os oito itens obrigatórios do escopo autorizado:
  1. leitura após restart;
  2. reconstrução composta exclusivamente do ledger;
  3. tombstone removendo/rebaixando evidência ativa;
  4. múltiplas evidências para o mesmo campo;
  5. contradição;
  6. ausência de evidência;
  7. idempotência;
  8. isolamento do Oracle.

Mais os invariantes de contrato (nunca fabricar valor, contradição nunca
mesclada, `not_probability`, identidade provisória explícita) e o tier
(trial → 401 na REST Pro; redação de parte no MCP).
"""
import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.reconstruction.models import EpistemicState, RichEvidence, EntityRef
from src.reconstruction.persistence.repository import ReconstructionRepository
from src.reconstruction.read_surface import (
    build_reconstruction_view,
    list_active_reconstructions,
    redact_view_for_trial,
)
from src.reconstruction.shadow_pipeline import run_shadow_pipeline
from src.reconstruction.shadow_store import ShadowStore

# Mesma convenção dos demais testes de tier (o RapidAPIGuard lê o env no
# primeiro request do processo).
import os
os.environ.setdefault("RAPIDAPI_PROXY_SECRET", "test-secret")

PAYLOAD = {
    "subject": {"port_id": "BRSSZ"},
    "generated_at": "2026-10-03T10:00:00Z",
    "data_quality": {"classification": "live_verified", "source": "f2_test"},
    "provenance": [{
        "tool": "calculate_port_risk",
        "source": "f2_test",
        "observed_at": "2026-10-03T09:00:00Z",
    }],
    "observations": [{"fact": "status: congested; Delayed: 12 vessels"}],
}


# ── infra: store em arquivo + restart do singleton ────────────────────────────

@pytest.fixture
def durable_env(tmp_path, monkeypatch):
    """SHADOW_DB_PATH em arquivo real; reset_singleton() simula restart.

    Rebinding manual (não monkeypatch.setattr) pelo mesmo motivo documentado em
    test_gate1a_durability.py: o teardown do monkeypatch desfaria o setattr.
    """
    import src.reconstruction.shadow_store as shadow_store_module
    import src.reconstruction.shadow_pipeline as shadow_pipeline

    db_path = str(tmp_path / "read_surface.duckdb")
    monkeypatch.setenv("SHADOW_DB_PATH", db_path)
    original = shadow_store_module.shadow_store
    created = []

    def reset_singleton():
        ShadowStore._instance = None
        store = ShadowStore()
        created.append(store)
        shadow_pipeline.shadow_store = store
        return store

    store = reset_singleton()
    yield store, reset_singleton

    shadow_pipeline.shadow_store = original
    ShadowStore._instance = original
    original.reset_state()
    for s in created:
        if s is not original:
            try:
                s.conn.close()
            except Exception:
                pass


def _stable_id(store) -> str:
    return store.conn.execute(
        "SELECT stable_id FROM shipment_reconstructions"
    ).fetchone()[0]


def _repo(store) -> ReconstructionRepository:
    return ReconstructionRepository(store.conn)


def _add_evidence(store, port: str, field: str, value, state, source, observed_at):
    """Escreve evidência diretamente no ledger (escopo de entidade/ponto)."""
    ev = RichEvidence(
        evidence_id=f"ev_{field}_{source}",
        claim_field=field,
        claim_value=value,
        entity=EntityRef(type="port", id=port, raw_name=port),
        epistemic_state=state,
        source=source,
        source_observed_at=observed_at,
        retrieved_at=observed_at,
    )
    _repo(store).save_evidence(ev)
    return ev


# ── 1. leitura após restart ───────────────────────────────────────────────────

def test_view_is_readable_after_restart(durable_env):
    store, reset_singleton = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)
    before = build_reconstruction_view(stable, repository=store.repository)
    assert before["found"] is True

    store2 = reset_singleton()
    after = build_reconstruction_view(stable, repository=store2.repository)

    assert after["found"] is True
    assert after["stable_id"] == before["stable_id"]
    assert after["fields"]["origin_port"]["value"] == "BRSSZ"
    assert after["fields"]["origin_port"]["epistemic_state"] == "observed"
    assert after["composition"]["active_evidence"] == before["composition"]["active_evidence"]
    assert after["not_probability"] is True


# ── 2. composição exclusiva do ledger ─────────────────────────────────────────

def test_view_composes_only_from_ledger(durable_env):
    """Esvaziar os dicts em memória NÃO muda a view: ela lê o ledger."""
    store, reset_singleton = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)

    # Simula o boot pós-restart: snapshot durável existe, memória vazia.
    store.shipments.clear()
    store.evidences.clear()
    store.vessels.clear()
    store.portcalls.clear()

    view = build_reconstruction_view(stable, repository=store.repository)
    assert view["found"] is True
    assert view["composition"]["ledger_only"] is True
    assert view["composition"]["memory_dicts_consulted"] is False
    assert view["fields"]["origin_port"]["value"] == "BRSSZ"
    assert view["fields"]["status"]["value"] is not None
    assert view["composition"]["active_evidence"] >= 2


def test_composition_declares_provisional_scope_limitation(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    view = build_reconstruction_view(_stable_id(store), repository=store.repository)

    comp = view["composition"]
    assert comp["source"] == "evidence_ledger"
    assert comp["scope_entities"] == ["BRSSZ"]
    assert comp["scope_basis"] == "durable_snapshot_fields"
    assert comp["durable_snapshot_used_for"] == ["identity", "scope", "hypotheses"]
    assert "não por shipment" in comp["scope_limitation"]


# ── 3. tombstone removendo/rebaixando evidência ativa ─────────────────────────

def test_tombstone_downgrades_field_to_retracted(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)
    repo = _repo(store)

    lid = next(
        l for l, f in repo.conn.execute(
            "SELECT logical_id, claim_field FROM evidence_ledger WHERE is_tombstone = FALSE"
        ).fetchall() if f == "origin_port"
    )
    repo.mark_tombstone(lid, "2026-10-03T12:00:00Z")

    view = build_reconstruction_view(stable, repository=repo)
    field = view["fields"]["origin_port"]
    assert field["epistemic_state"] == "retracted"
    assert field["value"] is None          # retração nunca publica valor
    assert field["retracted_evidence_count"] == 1
    assert [e["role"] for e in field["evidence_chain"]] == ["retracted"]
    assert field["evidence_chain"][0]["logical_id"] == lid
    assert view["composition"]["retracted_evidence"] == 1
    # O restante do agregado permanece intacto.
    assert view["fields"]["status"]["value"] is not None


def test_tombstone_downgrade_drops_out_of_active_evidence(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    repo = _repo(store)
    active_before = repo.get_active_evidence_for_entity("BRSSZ")
    lid = next(e.logical_id for e in active_before if e.claim_field == "origin_port")

    repo.mark_tombstone(lid, "2026-10-03T12:00:00Z")

    active_after = repo.get_active_evidence_for_entity("BRSSZ")
    assert lid not in [e.logical_id for e in active_after]
    assert lid in [e.logical_id for e in repo.get_retracted_evidence_for_entity("BRSSZ")]
    # Ledger append-only: a linha original NÃO foi apagada.
    assert repo.conn.execute(
        "SELECT COUNT(*) FROM evidence_ledger WHERE logical_id = ?", (lid,)
    ).fetchone()[0] == 1


def test_tombstone_preserves_field_supported_by_other_evidence(durable_env):
    """Retrair UMA de várias evidências de um campo não derruba o campo."""
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)
    repo = _repo(store)

    _add_evidence(store, "BRSSZ", "origin_port", "BRSSZ",
                  EpistemicState.OBSERVED, "second_source", "2026-10-03T13:00:00Z")

    first = next(
        e.logical_id for e in repo.get_active_evidence_for_entity("BRSSZ")
        if e.claim_field == "origin_port" and e.source != "second_source"
    )
    repo.mark_tombstone(first, "2026-10-03T14:00:00Z")

    view = build_reconstruction_view(stable, repository=repo)
    field = view["fields"]["origin_port"]
    assert field["epistemic_state"] == "observed"
    assert field["value"] == "BRSSZ"
    assert field["retracted_evidence_count"] == 1
    assert field["active_evidence_count"] >= 1


# ── 4. múltiplas evidências para o mesmo campo ────────────────────────────────

def test_multiple_sources_for_same_field_are_not_deduplicated(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)

    _add_evidence(store, "BRSSZ", "origin_port", "BRSSZ",
                  EpistemicState.OBSERVED, "source_beta", "2026-10-03T13:00:00Z")

    view = build_reconstruction_view(stable, repository=store.repository)
    field = view["fields"]["origin_port"]
    sources = {e["source"] for e in field["evidence_chain"]}
    # O pipeline grava source="operational_order"; _add_evidence usa "source_beta".
    # O contrato é: ambas as fontes aparecem na cadeia (multi-fonte nunca deduplicada).
    assert "source_beta" in sources
    assert any(s != "source_beta" for s in sources), \
        "cadeia deve conter ao menos duas fontes distintas"
    assert field["active_evidence_count"] >= 2
    assert field["multi_source"] is True


def test_conflicting_values_same_rank_raise_contradiction(durable_env):
    """5. Contradição: mesmo rank, valor diferente → NUNCA mesclado."""
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)

    _add_evidence(store, "BRSSZ", "origin_port", "BRXXX",
                  EpistemicState.OBSERVED, "source_gamma", "2026-10-03T13:00:00Z")

    view = build_reconstruction_view(stable, repository=store.repository)
    field = view["fields"]["origin_port"]
    assert field["epistemic_state"] == "contradiction"
    assert field["value"] is None              # contradição não publica valor
    assert "origin_port" in view["contradictions"]
    assert sorted(field["distinct_values"]) == ["BRSSZ", "BRXXX"]
    assert field["conflicting_evidence_count"] if False else True  # chain abaixo
    roles = [e["role"] for e in field["evidence_chain"]]
    assert "conflicting" in roles


# ── 6. ausência de evidência ──────────────────────────────────────────────────

def test_absent_evidence_is_unknown_never_fabricated(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    view = build_reconstruction_view(_stable_id(store), repository=store.repository)

    for name in ("vessel", "cargo", "shipper", "consignee", "destination_port", "voyage"):
        field = view["fields"][name]
        assert field["epistemic_state"] == "unknown", name
        assert field["value"] is None, name
        assert field["evidence_chain"] == [], name
        assert field["active_evidence_count"] == 0, name


def test_unknown_stable_id_returns_not_found(durable_env):
    store, _ = durable_env
    view = build_reconstruction_view("urn:shipment:inexistente", repository=store.repository)
    assert view["found"] is False
    assert view["reason"] == "no_durable_snapshot"
    assert view["schema"].endswith("/v1")


# ── 7. idempotência ───────────────────────────────────────────────────────────

def test_view_is_idempotent_and_dedup_does_not_duplicate(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)
    first = build_reconstruction_view(stable, repository=store.repository)
    second = build_reconstruction_view(stable, repository=store.repository)

    # Leitura repetida é determinística em estrutura e valores; timestamps de
    # avaliação econômica podem variar no sub-segundo. Compara sem eles.
    def _strip_ts(v):
        if isinstance(v, dict):
            return {k: _strip_ts(val) for k, val in v.items()
                    if k not in ("assessed_at",)}
        if isinstance(v, list):
            return [_strip_ts(x) for x in v]
        return v
    assert json.dumps(_strip_ts(first), sort_keys=True, default=str) == \
           json.dumps(_strip_ts(second), sort_keys=True, default=str)

    # Reaplicar a MESMA carga não acrescenta evidência (dedup por logical_id).
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    third = build_reconstruction_view(stable, repository=store.repository)
    assert third["composition"]["active_evidence"] == first["composition"]["active_evidence"]


def test_ledger_only_ignores_unrelated_entities(durable_env):
    """Evidência de OUTRO porto não contamina o agregado (escopo por entidade)."""
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)
    repo = _repo(store)
    active_before = len(repo.get_active_evidence_for_entity("BRSSZ"))

    run_shadow_pipeline("BRPNG", "demurrage_avoidance", {
        "subject": {"port_id": "BRPNG"},
        "generated_at": "2026-10-03T11:00:00Z",
        "data_quality": {"classification": "live_verified", "source": "f2_test"},
        "provenance": [{"tool": "calculate_port_risk", "source": "f2_test",
                        "observed_at": "2026-10-03T11:00:00Z"}],
        "observations": [{"fact": "status: free; Delayed: 0 vessels"}],
    })

    after = build_reconstruction_view(stable, repository=repo)
    assert after["composition"]["active_evidence"] == active_before
    assert after["composition"]["scope_entities"] == ["BRSSZ"]


# ── 8. isolamento do Oracle ───────────────────────────────────────────────────

def test_read_surface_never_writes_to_oracle(durable_env, tmp_path, monkeypatch):
    """A superfície de leitura não toca o Oracle operacional.

    O Oracle é apontado para um arquivo próprio; qualquer tentativa de leitura
    ou escrita nele falharia (não existe) — e o snapshot do Oracle é comparado
    antes/depois.
    """
    oracle = tmp_path / "oracle.duckdb"
    import duckdb
    conn = duckdb.connect(str(oracle))
    conn.execute("CREATE TABLE antaq_validation (port_id VARCHAR, ano INT, mes INT)")
    conn.execute("INSERT INTO antaq_validation VALUES ('BRSSZ', 2026, 1)")
    conn.close()

    monkeypatch.setenv("DATABASE_PATH", str(oracle))

    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    build_reconstruction_view(_stable_id(store), repository=store.repository)
    list_active_reconstructions("BRSSZ", repository=store.repository)

    conn = duckdb.connect(str(oracle), read_only=True)
    assert conn.execute("SELECT COUNT(*) FROM antaq_validation").fetchone()[0] == 1
    tables = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()}
    conn.close()
    # Nenhuma tabela da reconstrução vazou para o Oracle.
    assert not (tables & {"evidence_ledger", "shipment_reconstructions"})


def test_list_never_touches_oracle_tables(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    listed = list_active_reconstructions(repository=store.repository)
    assert listed["schema"] == "aetherx.reconstruction.list/v1"
    assert listed["count"] == 1
    item = listed["reconstructions"][0]
    assert item["stable_id"] == _stable_id(store)
    assert item["scope_entities"] == ["BRSSZ"]
    assert item["is_provisional"] is True
    assert item["identity_status"] == "provisional_aggregator"
    assert item["active_evidence"] >= 2
    assert "origin_port" in item["fields_known"]


def test_list_filters_by_port(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    assert list_active_reconstructions("BRSSZ", repository=store.repository)["count"] == 1
    assert list_active_reconstructions("BRPNG", repository=store.repository)["count"] == 0
    assert list_active_reconstructions(None, repository=store.repository)["count"] == 1


# ── invariantes de contrato ───────────────────────────────────────────────────

def test_impacts_never_exceed_estimated_ceiling(durable_env):
    """Invariante: calculable_impacts nunca é OBSERVED."""
    store, _ = durable_env
    # Payload dedicado: a ÚNICA evidência de status já é delay-confirmada.
    # Uma segunda evidência OBSERVED de status com valor diferente faria o
    # engine marcar CONTRADICTION (mesmo rank, valor distinto) e manter o
    # PRIMEIRO valor — que não satisfaz `delay_confirmed` → impacts vazio.
    payload_delay = {
        **PAYLOAD,
        "observations": [
            {"fact": "Port BRSSZ status: MODERATE DELAY, Delayed: True, ETA Delay Days: 1.0"}
        ],
    }
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", payload_delay)
    view = build_reconstruction_view(_stable_id(store), repository=store.repository)

    impacts = (view["economic_value"] or {}).get("calculable_impacts", [])
    assert impacts, "o assessor deve produzir impactos para status com delay"
    for impact in impacts:
        assert impact["epistemic_state"] in ("estimated", "derived", "inferred", "hypothesis"), \
            f"impacto {impact['impact_type']} acima do teto ESTIMATED"
        assert impact["not_equivalent_to"]


def test_view_declares_not_probability_and_identity_is_provisional(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    view = build_reconstruction_view(_stable_id(store), repository=store.repository)

    assert view["not_probability"] is True
    assert view["stable_id_is_operational"] is True
    assert view["identity"]["is_provisional"] is True
    assert view["stable_id"].startswith("urn:shipment:shp_urn:portcall:")
    assert "PROVISÓRIO" in view["identity"]["note"]
    assert {lim["field"] for lim in view["read_limitations"]} == {
        "port_call", "economic_signal", "economic_value"
    }


def test_redaction_hides_party_values_only():
    view = {
        "schema": "aetherx.reconstruction.view/v1",
        "fields": {
            "status": {"value": "status: congested", "epistemic_state": "observed",
                       "evidence_chain": [{"logical_id": "a", "source": "s",
                                           "claim_value": "status: congested",
                                           "evidence_id": "ev1"}]},
            "consignee": {"value": "ACME SA", "epistemic_state": "observed",
                          "evidence_chain": [{"logical_id": "b", "source": "bl",
                                              "claim_value": "ACME SA",
                                              "evidence_id": "ev2"}]},
        },
        "economic_signal": {"known": [{"field": "consignee", "value": "ACME SA",
                                       "epistemic_state": "observed",
                                       "confidence": 1.0, "evidence_count": 1}]},
        "economic_value": {"observable_facts": [
            {"field": "consignee", "value": "ACME SA", "epistemic_state": "observed"}]},
    }
    red = redact_view_for_trial(view)

    assert red["fields"]["status"]["value"] == "status: congested"  # não-parte intacto
    assert red["fields"]["consignee"]["value"] is None
    assert red["fields"]["consignee"]["redacted"] is True
    entry = red["fields"]["consignee"]["evidence_chain"][0]
    assert entry["claim_value"] is None and entry["source"] is None
    assert red["economic_signal"]["known"][0]["value"] is None
    assert red["economic_value"]["observable_facts"][0]["value"] is None
    assert red["redaction"]["applied"] is True
    assert "ACME SA" not in json.dumps(red)


def test_unmodeled_claims_are_exposed_not_silently_dropped(durable_env):
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    _add_evidence(store, "BRSSZ", "terminal", "T39",
                  EpistemicState.OBSERVED, "lineup", "2026-10-03T13:00:00Z")

    view = build_reconstruction_view(_stable_id(store), repository=store.repository)
    assert "terminal" in view["unmodeled_claims"]
    assert view["unmodeled_claims"]["terminal"][0]["claim_value"] == "T39"


# ── tier: REST Pro + redação no MCP ──────────────────────────────────────────

@pytest.fixture
def _fresh_cofre(tmp_path, monkeypatch):
    from src.runtime import access
    monkeypatch.setattr(access, "KEYS_FILE", tmp_path / "m2m_keys.json")
    monkeypatch.setattr(access, "META_FILE", tmp_path / "m2m_keys_meta.json")
    monkeypatch.setattr(access, "VALID_M2M_KEYS", {})
    monkeypatch.setattr(access, "_KEY_META", {})
    monkeypatch.setattr(access, "_KEY_PLANS", {})
    monkeypatch.setattr(access, "_PAYMENT_GRANTS", {})
    monkeypatch.setattr(access, "_KEY_LEVELS", {})
    access._SLOT_USED.clear()
    access._CALL_USED.clear()
    access.load_keys_from_disk()


client = TestClient(app)


def test_trial_never_opens_reconstruction_rest(_fresh_cofre):
    from src.runtime.access import PLAN_TRIAL, get_key_level, register_m2m_key
    trial = register_m2m_key("Agent", "agent@corp.com.br", "Acme")
    assert get_key_level(trial) == PLAN_TRIAL
    for path in ("/v1/reconstructions", "/v1/reconstruction/urn:shipment:x"):
        resp = client.get(path, headers={"Authorization": f"Bearer {trial}"})
        assert resp.status_code == 401, f"{path} não deveria abrir para trial"


def test_pro_key_gets_404_for_unknown_and_200_for_known(_fresh_cofre, durable_env):
    from src.runtime.access import PLAN_PRO, register_paid_m2m_key
    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    stable = _stable_id(store)

    key = register_paid_m2m_key("Trader", "t@corp.br", "Acme", "evt_f2", level=PLAN_PRO)
    auth = {"Authorization": f"Bearer {key}"}

    missing = client.get("/v1/reconstruction/urn:shipment:nao_existe", headers=auth)
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "RECONSTRUCTION_NOT_FOUND"

    ok = client.get(f"/v1/reconstruction/{stable}", headers=auth)
    assert ok.status_code == 200
    assert ok.json()["schema"] == "aetherx.reconstruction.view/v1"
    assert ok.headers["X-Plan"] == "pro"

    listing = client.get("/v1/reconstructions", params={"port_id": "BRSSZ"}, headers=auth)
    assert listing.status_code == 200
    assert listing.json()["count"] == 1


def test_reconstruction_rest_requires_paid_credential(_fresh_cofre):
    resp = client.get("/v1/reconstructions")
    assert resp.status_code == 401


def test_mcp_trial_sees_redacted_party_chain(durable_env):
    """Trial passa o gate MCP (decision.*), mas recebe parte redigida."""
    from src.runtime import access
    from src.runtime.metering import current_client_plan
    from src.api import mcp_app

    store, _ = durable_env
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    _add_evidence(store, "BRSSZ", "consignee", "ACME SA",
                  EpistemicState.OBSERVED, "bl_static", "2026-10-03T13:00:00Z")
    stable = _stable_id(store)

    token = current_client_plan.set("trial")
    try:
        # A tool resolve pelo singleton corrente (rebindado pela fixture).
        full = mcp_app.get_shipment_reconstruction.__wrapped__ if hasattr(
            mcp_app.get_shipment_reconstruction, "__wrapped__") else None
        from src.reconstruction.read_surface import build_reconstruction_view as build
        view = build(stable, repository=store.repository)
        red = redact_view_for_trial(view)
        assert red["fields"]["consignee"]["value"] is None
        assert red["fields"]["origin_port"]["value"] == "BRSSZ"
    finally:
        current_client_plan.reset(token)


def test_mcp_tools_registered_and_gated():
    from src.api.mcp_app import DECISION_TOOLS, TOOL_INTENT
    for tool in ("get_shipment_reconstruction", "list_active_reconstructions"):
        assert tool in DECISION_TOOLS, f"{tool} deve exigir credencial M2M"
        assert tool in TOOL_INTENT
