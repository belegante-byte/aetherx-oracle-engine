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
