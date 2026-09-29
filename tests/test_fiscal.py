import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.products.gp5.fiscal import evaluate_fiscal_routing

client = TestClient(app)

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
