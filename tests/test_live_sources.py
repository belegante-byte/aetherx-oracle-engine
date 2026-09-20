import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest

from src.ingestion.live_sources import (
    APPA_SECOES,
    normalizar_carga,
    TO_STATUS,
    fetch_appa_lineup,
    fetch_santos_atracacoes,
    fetch_lachmann_schedule,
    fetch_silog_pre_pauta,
    fetch_shipinfo_congestion,
    resumo_por_porto,
    _is_current_santos_painel_row,
    _parse_santos_painel_dt,
)
from scripts.run_ingestion_live import _score_from_status


def test_normalizar_carga_soja():
    assert normalizar_carga("SOJA A GRANEL") == "SOJA (GRAO)"
    assert normalizar_carga("ÓLEO DE SOJA") == "OLEO DE SOJA"
    assert normalizar_carga("FARELO DE SOJA") == "FARELO DE SOJA"
    assert normalizar_carga("CONTÊINER CHEIO") == "CONTEINERES"
    assert normalizar_carga(None) == "DESCONHECIDA"
    assert normalizar_carga("") == "DESCONHECIDA"


def test_to_status_mapping():
    assert TO_STATUS["ao_largo"] == "AO_LARGO"
    assert TO_STATUS["atracados"] == "ATRACADO"
    assert TO_STATUS["esperados"] == "ESPERADO"
    assert TO_STATUS["em_operacao"] == "EM_OPERACAO"


def test_appa_lineup_real_has_sections():
    try:
        dados = fetch_appa_lineup()
    except Exception as e:  # APPA é fonte externa; tolera indisponibilidade transitória
        pytest.skip(f"APPA indisponível nesta execução: {type(e).__name__}")
    for secao in ("atracados", "ao_largo", "esperados", "programados"):
        assert secao in dados
    assert len(dados.get("atracados", [])) > 0


def test_appa_voos_tem_imo_ou_navio():
    try:
        dados = fetch_appa_lineup()
    except Exception as e:
        pytest.skip(f"APPA indisponível nesta execução: {type(e).__name__}")
    registros = dados.get("atracados", []) or dados.get("ao_largo", [])
    assert registros
    r = registros[0]
    # APPA traz embarcação e IMO em campos próprios.
    texto = " ".join(str(v) for v in r.values())
    assert any(ch.isdigit() for ch in texto)


def test_santos_atracacoes_real_tem_imo():
    try:
        linhas = fetch_santos_atracacoes()
    except Exception as e:
        pytest.skip(f"Santos indisponível nesta execução: {type(e).__name__}")
    assert linhas
    assert all(l["port_id"] == "BRSSZ" for l in linhas)
    assert any(l["imo"] for l in linhas)


def test_lachmann_schedule_retorna_esperados():
    try:
        linhas = fetch_lachmann_schedule()
    except Exception as e:
        pytest.skip(f"Lachmann indisponível nesta execução: {type(e).__name__}")
    assert isinstance(linhas, list)
    for l in linhas:
        assert l["port_id"] == "BRPNG"
        assert l["source"] == "lachmann"
        assert l["vessel_name"]


def test_score_from_status_deriva_fila_real():
    resumo = {
        "total": 100,
        "status_AO_LARGO": 20,
        "status_ESPERADO": 60,
        "status_ATRACADO": 20,
        "src_appa": 100,
    }
    met = _score_from_status("BRPNG", resumo, {"appa": {"ok": True}})
    # Fila REAL = AO_LARGO (esperados = chegadas futuras, não soma)
    assert met["waiting_vessels"] == 20
    assert met["ao_largo"] == 20
    assert met["atracados"] == 20
    assert met["congestion_score"] > 0.05
    assert met["eta_delay_days"] == 2.0  # fila real 20 -> 1.2 + 20*0.04


def test_score_from_status_sem_fila():
    resumo = {
        "total": 10,
        "status_ATRACADO": 10,
        "status_EM_OPERACAO": 0,
        "src_santos": 10,
    }
    met = _score_from_status("BRSSZ", resumo, {"santos": {"ok": True}})
    assert met["waiting_vessels"] == 0
    assert met["congestion_score"] < 0.5


def test_silog_riio_retorna_linhas_com_imo():
    try:
        linhas = fetch_silog_pre_pauta(1)
    except Exception as e:
        pytest.skip(f"SILOG PortosRio indisponível nesta execução: {type(e).__name__}")
    assert linhas
    assert all(l["port_id"] == "BRRIO" for l in linhas)
    assert all(l["source"] == "portosrio_silog" for l in linhas)
    assert all(l["vessel_name"] for l in linhas)
    assert any(l["imo"] for l in linhas)


def test_resumo_por_porto_agrupa():
    linhas = [
        {"port_id": "BRPNG", "status": "ao_largo", "source": "appa"},
        {"port_id": "BRPNG", "status": "esperados", "source": "appa"},
        {"port_id": "BRPNG", "status": "esperados", "source": "lachmann"},
        {"port_id": "BRSSZ", "status": "em_operacao", "source": "santos_painel"},
    ]
    res = resumo_por_porto(linhas)
    assert res["BRPNG"]["total"] == 3
    assert res["BRPNG"]["status_AO_LARGO"] == 1
    assert res["BRPNG"]["status_ESPERADO"] == 2
    assert res["BRPNG"]["src_lachmann"] == 1
    assert res["BRSSZ"]["status_EM_OPERACAO"] == 1

def test_silog_fundeio_conta_como_ao_largo():
    """Regressão: navio com 'Fundeio' no contexto (de/para) é fila real (ao_largo),
    mesmo que o tipo de operação seja MUDANÇA/SAÍDA/ENTRADA."""
    from collections import Counter
    try:
        linhas = fetch_silog_pre_pauta(1)  # BRRIO
    except Exception as e:
        pytest.skip(f"SILOG indisponível nesta execução: {type(e).__name__}")
    assert linhas, "esperava linhas SILOG para BRRIO"
    status = Counter(l["status"] for l in linhas)
    # com a correção, deve haver ao_largo (navios fundeados) — se a fonte tiver fundeados
    # A validação real: pelo menos um navio 'Fundeio' vira ao_largo
    fundeados = [l for l in linhas if "FUNDE" in (l["raw"].get("de","") + l["raw"].get("para","")).upper()]
    if fundeados:
        assert all(l["status"] == "ao_largo" for l in fundeados), "Fundeio deveria ser ao_largo"
    # se a fonte tem fundeados hoje, ao_largo > 0
    if any("FUNDE" in (l["raw"].get("de","") + l["raw"].get("para","")).upper() for l in linhas):
        assert status.get("ao_largo", 0) > 0


def test_santos_painel_current_row_filter():
    now = datetime(2026, 9, 19, 18, 30)
    current = {
        "Navio": "GREEN OSAKA",
        "Status": "OPERANDO",
        "Atracação": now.strftime("%d/%m/%y %H:%M:%S"),
        "Estimativa Fim Oper.": (now + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
    }
    old = {
        "Navio": "PACIFIC AZUR",
        "Status": "AG DESATRACACAO",
        "Atracação": "01/01/25 12:55:00",
        "Estimativa Fim Oper.": "2025-01-02 11:12:00",
    }
    completed = {
        "Navio": "OLD VESSEL",
        "Status": "DESATRACACAO",
        "Atracação": now.strftime("%d/%m/%y %H:%M:%S"),
        "Estimativa Fim Oper.": (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    }
    stale = {
        "Navio": "STALE VESSEL",
        "Status": "OPERANDO",
        "Atracação": (now - timedelta(days=2)).strftime("%d/%m/%y %H:%M:%S"),
        "Estimativa Fim Oper.": (now - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S"),
    }
    assert _is_current_santos_painel_row(current, now) is True
    assert _is_current_santos_painel_row(old, now) is False
    assert _is_current_santos_painel_row(completed, now) is False
    assert _is_current_santos_painel_row(stale, now) is False


def test_santos_painel_date_parser_handles_mixed_formats():
    assert _parse_santos_painel_dt("01/01/25 12:55:00") == datetime(2025, 1, 1, 12, 55)
    assert _parse_santos_painel_dt("2025-01-02 11:12:00") == datetime(2025, 1, 2, 11, 12)
    assert _parse_santos_painel_dt("") is None
    assert _parse_santos_painel_dt(None) is None


def test_shipinfo_collector_disabled_by_default(monkeypatch):
    import src.ingestion.live_sources as ls

    def fail_get(*args, **kwargs):
        raise AssertionError("shipinfo não deve chamar rede quando desabilitado")

    monkeypatch.setattr(ls, "_shipinfo_get", fail_get)
    monkeypatch.setattr(ls, "SHIPINFO_ENABLED", False)
    assert fetch_shipinfo_congestion() == []
