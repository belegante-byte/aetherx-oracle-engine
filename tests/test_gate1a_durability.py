"""
Gate 1A — Durabilidade da persistência da reconstrução.

Contrato (docs/architecture/reconstruction-persistence-contract.md):
  1. Escrever via run_shadow_pipeline em SHADOW_DB_PATH de arquivo.
  2. Reiniciar a instância (novo singleton, nova conexão ao mesmo arquivo)
     → contadores e a reconstrução inteira são recuperados.
  3. Idempotência: reaplicar a mesma evidência não duplica nada no ledger.
  4. Tombstone rebaixa campo e sobrevive a restart (append-only).
"""
import duckdb
import pytest

import src.reconstruction.shadow_pipeline as shadow_pipeline
from src.reconstruction.shadow_pipeline import run_shadow_pipeline
from src.reconstruction.shadow_store import ShadowStore


PAYLOAD = {
    "subject": {"port_id": "BRSSZ"},
    "generated_at": "2026-10-03T10:00:00Z",
    "data_quality": {"classification": "live_verified", "source": "gate1a_test"},
    "provenance": [{
        "tool": "calculate_port_risk",
        "source": "gate1a_test",
        "observed_at": "2026-10-03T09:00:00Z",
    }],
    "observations": [{"fact": "status: congested; Delayed: 12 vessels"}],
}


@pytest.fixture
def durable_env(tmp_path, monkeypatch):
    """SHADOW_DB_PATH em arquivo; singleton reinicia a cada reset_singleton().

    O rebinding de `shadow_pipeline.shadow_store` é manual (não via
    monkeypatch.setattr): o teardown do monkeypatch roda DEPOIS deste finally e
    desfaria o setattr, devolvendo o store file-backed aos testes seguintes.
    """
    db_path = str(tmp_path / "gate1a.duckdb")
    monkeypatch.setenv("SHADOW_DB_PATH", db_path)

    import src.reconstruction.shadow_store as shadow_store_module
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

    # Restaura a identidade do singleton original em TODOS os importadores
    # (shadow_pipeline e mcp_app capturam a referência no import).
    shadow_pipeline.shadow_store = original
    ShadowStore._instance = original
    original.reset_state()
    for s in created:
        if s is not original:
            try:
                s.conn.close()
            except Exception:
                pass


def _ledger_count(conn):
    return conn.execute(
        "SELECT COUNT(*) FROM evidence_ledger WHERE is_tombstone = FALSE"
    ).fetchone()[0]


@pytest.fixture
def in_memory_env(monkeypatch):
    """Store :memory: isolado — o default do processo de teste."""
    monkeypatch.delenv("SHADOW_DB_PATH", raising=False)

    import src.reconstruction.shadow_store as shadow_store_module
    original = shadow_store_module.shadow_store

    ShadowStore._instance = None
    store = ShadowStore()
    shadow_pipeline.shadow_store = store
    yield store

    shadow_pipeline.shadow_store = original
    ShadowStore._instance = original
    original.reset_state()
    store.conn.close()


def test_reset_state_clears_in_memory_ledger(in_memory_env):
    """Regressão: o store agora possui o ledger durável. Sem limpá-lo no
    reset_state(), evidências de um teste deduplicam a carga do seguinte —
    `new_evidence` fica 0 com `orders_processed` = 1 (flaky por ordem)."""
    store = in_memory_env

    run_shadow_pipeline("BRSSZ", "routing", PAYLOAD)
    assert store.get_metrics()["new_evidence"] > 0
    assert _ledger_count(store.conn) > 0

    store.reset_state()

    assert store.get_metrics()["new_evidence"] == 0
    assert _ledger_count(store.conn) == 0
    assert store.conn.execute(
        "SELECT COUNT(*) FROM shipment_reconstructions"
    ).fetchone()[0] == 0

    # A mesma carga após o reset volta a ser nova — não deduplicada.
    run_shadow_pipeline("BRSSZ", "routing", PAYLOAD)
    assert store.get_metrics()["new_evidence"] > 0
    assert store.get_metrics()["deduplicated_evidence"] == 0


def test_write_then_restart_recovers_reconstruction(durable_env):
    store, reset_singleton = durable_env

    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    m1 = store.get_metrics()
    assert m1["new_evidence"] >= 2  # origin_port + status
    assert m1["new_shipments"] == 1
    shipment_key = next(iter(store.shipments.keys()))
    ledger_before = _ledger_count(store.conn)
    assert ledger_before == m1["new_evidence"]

    # --- restart: nova instância, mesma conexão lógica ao arquivo ---
    store2 = reset_singleton()
    assert store2 is not store

    # Contadores sobrevivem ao restart.
    m2 = store2.get_metrics()
    for metric, value in m1.items():
        assert m2[metric] == value, f"counter {metric} lost on restart"

    # Reconstrução inteira recuperada do snapshot durável.
    recovered = store2.load_shipment(f"urn:shipment:{shipment_key}")
    assert recovered is not None
    assert recovered.origin_port.current_value == "BRSSZ"
    assert recovered.origin_port.state.value == "observed"
    assert recovered.status.current_value is not None
    assert len(recovered.evidence_store) == m1["new_evidence"]
    assert _ledger_count(store2.conn) == ledger_before


def test_idempotency_survives_restart(durable_env):
    store, reset_singleton = durable_env

    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    m1 = store.get_metrics()
    ledger_before = _ledger_count(store.conn)

    store2 = reset_singleton()

    # Mesma carga após restart → 100% deduplicada, nada novo no ledger.
    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    m2 = store2.get_metrics()
    assert m2["new_evidence"] == m1["new_evidence"]
    assert m2["deduplicated_evidence"] == m1["new_evidence"]
    assert _ledger_count(store2.conn) == ledger_before

    # O snapshot do shipment não divergiu (campos idênticos).
    shipment_key = next(iter(store2.shipments.keys()))
    recovered = store2.load_shipment(f"urn:shipment:{shipment_key}")
    assert recovered.origin_port.current_value == "BRSSZ"
    assert len(recovered.evidence_store) == m1["new_evidence"]


def test_tombstone_downgrade_survives_restart(durable_env):
    store, reset_singleton = durable_env

    run_shadow_pipeline("BRSSZ", "demurrage_avoidance", PAYLOAD)
    store2 = reset_singleton()

    rows = store2.conn.execute(
        "SELECT logical_id, claim_field FROM evidence_ledger WHERE is_tombstone = FALSE"
    ).fetchall()
    target = next(lid for lid, field in rows if field == "origin_port")

    # Retração append-only: a evidência permanece, a linha nova é a marca.
    from src.reconstruction.persistence.repository import ReconstructionRepository
    ReconstructionRepository(store2.conn).mark_tombstone(target, "2026-10-03T11:00:00Z")
    active_before = store2.conn.execute(
        "SELECT COUNT(*) FROM evidence_ledger"
    ).fetchone()[0]
    assert store2.conn.execute(
        "SELECT COUNT(*) FROM evidence_ledger WHERE logical_id = ?", (target,)
    ).fetchone()[0] == 1

    store3 = reset_singleton()
    assert store3.conn.execute(
        "SELECT COUNT(*) FROM evidence_ledger"
    ).fetchone()[0] == active_before

    # Campo rebaixado: a evidência tombada sai da leitura ativa da entidade.
    active = ReconstructionRepository(store3.conn).get_active_evidence_for_entity("BRSSZ")
    assert target not in [ev.logical_id for ev in active]
    assert len(active) == len(rows) - 1

    # O shipment durável é lido do banco (os dicts em memória não são
    # repovoados no boot — apenas contadores e as tabelas do repositório).
    stable_id = store3.conn.execute(
        "SELECT stable_id FROM shipment_reconstructions"
    ).fetchone()[0]
    recovered = store3.load_shipment(stable_id)
    assert recovered is not None
    assert recovered.stable_id == stable_id
    assert stable_id.startswith("urn:shipment:")
