"""Teste da tool batedora de intenção simples get_port_operations_status.

Garante que a resposta é honesta: usa os mesmos dados vivos de
calculate_port_risk, expõe provenance (data_source/as_of) e o upsell da
camada de decisão é factual (sem inventar rastreio por IMO/MMSI).
"""
from src.api.mcp_app import get_port_operations_status


def test_get_port_operations_status_shape_brssz():
    res = get_port_operations_status("BRSSZ")
    assert res["port_id"] == "BRSSZ"
    assert res["status"] in {"NORMAL", "MODERATE_DELAY", "CONGESTED"}
    assert isinstance(res["is_delayed"], bool)
    assert "eta_delay_days" in res
    assert "waiting_vessels" in res
    assert "data_source" in res and res["data_source"]
    assert "as_of" in res


def test_get_port_operations_status_upsell_is_factual():
    res = get_port_operations_status("BRPNG")
    dl = res["decision_layer"]
    assert dl["available"] is True
    assert dl["requires_m2m_key"] is True
    assert "evaluate_fiscal_routing" in dl["tools"]
    assert "evaluate_charter_risk" in dl["tools"]
    assert "request_m2m_key" in dl["hint"]
    # A tool NÃO afirma rastreio individual de embarcação (não temos AIS/IMO).
    assert "IMO" not in str(res)


def test_get_port_operations_status_uppercases():
    res = get_port_operations_status("brssz")
    assert res["port_id"] == "BRSSZ"