import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest

from src.ingestion.live_sources import (
    APPA_SECOES,
    normalizar_carga,
    TO_STATUS,
    fetch_appa_lineup,
    fetch_santos_atracacoes,
    fetch_lachmann_schedule,
    resumo_por_porto,
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
    dados = fetch_appa_lineup()
    for secao in ("atracados", "ao_largo", "esperados", "programados"):
        assert secao in dados
    assert len(dados.get("atracados", [])) > 0


def test_appa_voos_tem_imo_ou_navio():
    dados = fetch_appa_lineup()
    registros = dados.get("atracados", []) or dados.get("ao_largo", [])
    assert registros
    r = registros[0]
    # APPA traz embarcação e IMO em campos próprios.
    texto = " ".join(str(v) for v in r.values())
    assert any(ch.isdigit() for ch in texto)


def test_santos_atracacoes_real_tem_imo():
    linhas = fetch_santos_atracacoes()
    assert linhas
    assert all(l["port_id"] == "BRSSZ" for l in linhas)
    assert any(l["imo"] for l in linhas)


def test_lachmann_schedule_retorna_esperados():
    linhas = fetch_lachmann_schedule()
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
    assert met["waiting_vessels"] == 80
    assert met["ao_largo"] == 20
    assert met["atracados"] == 20
    assert met["data_source"].startswith("live:")
    assert met["congestion_score"] > 0.05
    assert met["eta_delay_days"] >= 2.4


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