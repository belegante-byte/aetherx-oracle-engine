import duckdb
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.products.gp5 import fiscal
from src.products.gp5.fiscal import evaluate_fiscal_routing

client = TestClient(app)

FX = 5.22  # mesmo default de USD_BRL_FX em fiscal.py

def test_evaluate_fiscal_routing_logic():
    # Test valid input
    res = evaluate_fiscal_routing(intended_port_id="BRSSZ", commodity="FERTILIZANTES", cargo_value_usd=10000000.0, inland_uf="MT", cargo_tons=60000.0)
    assert res.schema_version == "fiscal-routing.v1"
    assert res.inland_uf == "MT"
    
    # Test exception on negative cargo
    with pytest.raises(ValueError):
        evaluate_fiscal_routing(intended_port_id="BRSSZ", commodity="FERTILIZANTES", cargo_value_usd=-500, inland_uf="MT", cargo_tons=60000.0)

def test_fiscal_routing_auth_required():
    # Calling the REST endpoint without token should return 403 Access Denied
    resp = client.get("/v1/gp5/fiscal-routing?intended_port_id=BRSSZ&commodity=FERTILIZANTES")
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]


def test_fiscal_routing_summary_leads_with_real_driver():
    # ICMS é apurado pelo destino (inland_uf) e é idêntico entre as opções;
    # a prosa não pode mais citar "ICMS de X% vs Y%" como motivo principal.
    res = evaluate_fiscal_routing(
        intended_port_id="BRSSZ", commodity="FERTILIZANTES",
        cargo_value_usd=10000000.0, inland_uf="MT", cargo_tons=60000.0,
    )
    summary = res.recommendation_summary
    assert summary.startswith("Alerta de Arbitragem: Redirecionar carga de")
    assert "Motivo principal" in summary
    assert "frete terrestre" in summary, "frete é o driver dominante (mock de rate_ton)"
    assert "ICMS de" not in summary, "ICMS nunca diferencia opções no modelo atual"


def test_fiscal_routing_summary_savings_math():
    # savings da prosa deve ser exatamente a diferença entre os totais das opções.
    res = evaluate_fiscal_routing(
        intended_port_id="BRSSZ", commodity="FERTILIZANTES",
        cargo_value_usd=10000000.0, inland_uf="MT", cargo_tons=60000.0,
    )
    best = min(res.options, key=lambda o: o.total_cost_usd)
    intended = next(o for o in res.options if o.port_id == res.intended_port_id)
    expected = round(intended.total_cost_usd - best.total_cost_usd, 2)
    assert f"US$ {expected:,.2f}" in res.recommendation_summary


# -----------------------------------------------------------------------------
# FASE 2 (Fretes Reais): corredores da CONAB/Sifreca em R$/t -> USD/t. O teste
# cria um DuckDB tmp com apenas a tabela freight_rates e aponta fiscal.DB_PATH
# para ele; o risco/demurrage continua vindo do oráculo real (DB_PATH default).
# -----------------------------------------------------------------------------

_REAL_CORRIDORS = [
    # (origin_uf, port_id, rate_brl_per_ton, source, reference_date, is_estimate)
    ("MT", "BRSSZ", 510.0, "CONAB Boletim Logístico 07/2026 (Sorriso-Santos)", "2026-07", False),
    ("MT", "BRPNG", 500.0, "CONAB Boletim Logístico 07/2026 (Sorriso-Paranaguá)", "2026-07", False),
    ("MS", "BRRGD", 250.0, "Estimativa Sifreca R$/t.km (sem rota publicada MS-Rio Grande)", "2026-07", True),
]


def _freight_db(tmp_path, rows):
    db = tmp_path / "freight.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute("""
        CREATE TABLE freight_rates (
            origin_uf VARCHAR, port_id VARCHAR, rate_brl_per_ton DOUBLE,
            mode VARCHAR, source VARCHAR, reference_date VARCHAR, is_estimate BOOLEAN,
            PRIMARY KEY (origin_uf, port_id))
    """)
    conn.executemany(
        "INSERT INTO freight_rates VALUES (?, ?, ?, 'rodoviário', ?, ?, ?)",
        rows,
    )
    conn.close()
    return db


def test_freight_real_corridor_conab_rate(tmp_path, monkeypatch):
    db = _freight_db(tmp_path, _REAL_CORRIDORS)
    monkeypatch.setattr(fiscal, "DB_PATH", str(db))
    res = evaluate_fiscal_routing(
        intended_port_id="BRSSZ", commodity="SOJA",
        cargo_value_usd=10000000.0, inland_uf="MT", cargo_tons=60000.0,
    )
    opt = next(o for o in res.options if o.port_id == "BRSSZ")
    assert opt.inland_freight_is_real is True, "corredor MT-Santos não é marcado real"
    assert "CONAB" in opt.inland_freight_source
    assert opt.inland_freight_as_of == "2026-07"
    # 510 R$/t / 5,22 = ~97,7 USD/t — longe do mock de 45 que o produto usava.
    assert abs(opt.inland_freight_rate_usd_per_ton - (510.0 / FX)) < 0.01
    assert opt.inland_freight_cost_usd == round(60000.0 * opt.inland_freight_rate_usd_per_ton, 2)


def test_freight_estimate_corridor_flagged(tmp_path, monkeypatch):
    db = _freight_db(tmp_path, _REAL_CORRIDORS)
    monkeypatch.setattr(fiscal, "DB_PATH", str(db))
    res = evaluate_fiscal_routing(
        intended_port_id="BRSSZ", commodity="SOJA",
        cargo_value_usd=10000000.0, inland_uf="MS", cargo_tons=60000.0,
    )
    opt = next(o for o in res.options if o.port_id == "BRRGD")
    assert opt.inland_freight_is_real is False, "estimativa deve ser marcada is_real=False"
    assert "Estimativa" in opt.inland_freight_source


def test_freight_missing_table_falls_back_to_legacy_flag(tmp_path, monkeypatch):
    # Snapshot binário antigo (data/oracle.duckdb commitado) não tem a tabela
    # freight_rates; a degradação precisa ser EXPLÍCITA, nunca silenciosa.
    db = tmp_path / "empty.duckdb"
    duckdb.connect(str(db)).close()
    monkeypatch.setattr(fiscal, "DB_PATH", str(db))
    res = evaluate_fiscal_routing(
        intended_port_id="BRSSZ", commodity="SOJA",
        cargo_value_usd=10000000.0, inland_uf="MT", cargo_tons=60000.0,
    )
    opt = next(o for o in res.options if o.port_id == "BRSSZ")
    assert opt.inland_freight_is_real is False
    assert "LEGACY_MOCK_FALLBACK" in opt.inland_freight_source
    assert len(res.options) >= 4, "sem a tabela o motor ainda deve responder"
