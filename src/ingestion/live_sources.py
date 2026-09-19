"""Fontes vivas de dados portuários para o Aether-X Oracle.

Integra fontes públicas reais (validadas no GP5) para os portos brasileiros:
- APPA Paranaguá (line-up ao vivo: atracados / ao largo / esperados, com IMO)
- Porto de Santos (atracações programadas com IMO + painel de operações)
- Lachmann (schedule ETA real de Paranaguá em XLS)

A ingestão é voluntariamente simples e resiliente: cada coletor retorna
listas de dicts; falha de uma fonte NÃO derruba as demais. Nenhuma fonte
requer chave de API.
"""

import io
import re
import ssl
import urllib.request
from datetime import datetime
from typing import Optional

import pandas as pd
from bs4 import BeautifulSoup

APPA_URL = "https://www.appaweb.appa.pr.gov.br/appaweb/pesquisa.aspx?WCI=relLineUpRetroativo"
LACHMANN_URL = "https://www.lachmann.com.br/arquivos_download/schedules_deadlines/Schedule_e_Deadlines_Paranagua.xls"
SANTOS_ATRACACOES_URL = (
    "https://www.portodesantos.com.br/informacoes-operacionais/"
    "operacoes-portuarias/navegacao-e-movimento-de-navios/atracacoes-programadas/"
)
SANTOS_PAINEL_URL = (
    "https://www.portodesantos.com.br/painel-de-monitoramento-das-operacoes-portuarias/"
)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

TO_STATUS = {
    "atracados": "ATRACADO",
    "programados": "PROGRAMADO",
    "ao_largo_reatracacao": "AO_LARGO",
    "ao_largo": "AO_LARGO",
    "esperados": "ESPERADO",
    "apoio": "APOIO",
    "despachados": "DESPACHADO",
    "esperado": "ESPERADO",
    "programado": "PROGRAMADO",
    "em_operacao": "EM_OPERACAO",
}


def _fetch(url: str, timeout: int = 30, binary: bool = False):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        data = resp.read()
    return data if binary else data.decode("utf-8", errors="replace")


def _parse_br_number(s: Optional[str]) -> float:
    if not s:
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    m = re.search(r"[\d.]+", s)
    return float(m.group(0)) if m else 0.0


# ---------------------------------------------------------------- APPA

APPA_SECOES = {
    "ATRACADOS": "atracados",
    "PROGRAMADOS": "programados",
    "AO LARGO PARA REATRACAÇÃO": "ao_largo_reatracacao",
    "AO LARGO": "ao_largo",
    "ESPERADOS": "esperados",
    "APOIO PORTUÁRIO / OUTROS": "apoio",
    "DESPACHADOS": "despachados",
}


def fetch_appa_lineup(timeout: int = 30) -> dict:
    """Retorna {secao: [registros]} do line-up ao vivo da APPA Paranaguá."""
    html = _fetch(APPA_URL, timeout=timeout)
    soup = BeautifulSoup(html, "html.parser")
    resultado = {}
    for table in soup.select("table"):
        th = table.select_one("thead th[colspan]") or table.select_one("thead tr th")
        if not th:
            continue
        titulo = th.get_text().strip().upper()
        chave = APPA_SECOES.get(titulo)
        if chave is None:
            continue
        header_rows = table.select("thead tr")
        colunas = (
            [c.get_text().strip() for c in header_rows[-1].select("th")]
            if header_rows else []
        )
        registros = []
        for row in table.select("tbody tr"):
            valores = [c.get_text().strip() for c in row.select("td")]
            registro = {}
            for i, v in enumerate(valores):
                nome = colunas[i] if i < len(colunas) else f"col_{i}"
                registro[nome] = v
            if registro:
                registros.append(registro)
        resultado[chave] = registros
    return resultado


def normalizar_carga(mercadoria: Optional[str]) -> str:
    if not mercadoria:
        return "DESCONHECIDA"
    m = mercadoria.upper().strip()
    if "OLEO DE SOJA" in m or "ÓLEO DE SOJA" in m:
        return "OLEO DE SOJA"
    if "FARELO DE SOJA" in m:
        return "FARELO DE SOJA"
    if "SOJA" in m:
        return "SOJA (GRAO)"
    if "CONTAINER" in m or "CONTÊINER" in m or "CONTENTORES" in m:
        return "CONTEINERES"
    if "CLORETO" in m and "POTASSIO" in m:
        return "CLORETO DE POTASSIO (FERTILIZANTE)"
    if "UREIA" in m:
        return "UREIA (FERTILIZANTE)"
    if "SULFATO DE AMONIO" in m:
        return "SULFATO DE AMONIO (FERTILIZANTE)"
    if "ACUCAR" in m or "AÇÚCAR" in m:
        return "ACUCAR"
    if "DIESEL" in m:
        return "OLEO DIESEL"
    if "METANOL" in m:
        return "METANOL"
    return m


def appa_para_raw_rows(port_id: str = "BRPNG", timeout: int = 30) -> list:
    """APPA -> linhas normalizadas de line-up (com IMO quando disponível)."""
    dados = fetch_appa_lineup(timeout=timeout)
    linhas = []
    for secao, registros in dados.items():
        for r in registros:
            imo_raw = r.get("IMO") or r.get("im") or ""
            imo = re.sub(r"[^0-9]", "", str(imo_raw)) or None
            vessel = (r.get("Código") or r.get("Navio") or r.get("Embarcação") or "DESCONHECIDO").upper()
            cargo_raw = r.get("Mercadoria") or r.get("Carga") or "DESCONHECIDA"
            cargo = normalizar_carga(cargo_raw)
            agente = (r.get("Agência") or r.get("Agente") or "NÃO CONFIRMADO").upper()
            dwt = _parse_br_number(r.get("DWT"))
            linhas.append({
                "port_id": port_id,
                "source": "appa",
                "vessel_name": vessel,
                "imo": imo,
                "status": secao,
                "cargo": cargo,
                "agency": agente,
                "dwt": dwt,
                "raw": r,
            })
    return linhas


# ---------------------------------------------------------------- Lachmann

def fetch_lachmann_schedule(timeout: int = 60) -> list:
    """Baixa o XLS de ETAs reais da Lachmann (Paranaguá) e extrai navios."""
    data = _fetch(LACHMANN_URL, timeout=timeout, binary=True)
    df = pd.read_excel(io.BytesIO(data), header=None)
    navios = []
    header_idx = None
    for i, row in df.iterrows():
        valores = [str(v) for v in row.values if pd.notna(v)]
        if any(k in " ".join(valores).upper() for k in ("MV", "SV", "ETA")) and "ETA" in " ".join(valores).upper():
            header_idx = i
            break
    if header_idx is None:
        return navios
    colunas_raw = [str(v) for v in df.iloc[header_idx].values]
    for i in range(header_idx + 1, len(df)):
        row = df.iloc[i]
        val = [v if pd.notna(v) else None for v in row.values]
        if not any(val):
            continue
        vessel = next((str(v).strip() for v in val[1:4] if isinstance(v, str) and re.search(r"[A-Z]{3,}", v)), None)
        if not vessel:
            continue
        eta = None
        for v in val:
            if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}", v):
                eta = v[:10]
                break
            if isinstance(v, pd.Timestamp):
                eta = v.strftime("%Y-%m-%d")
                break
        navios.append({
            "port_id": "BRPNG",
            "source": "lachmann",
            "vessel_name": vessel.upper(),
            "imo": None,
            "status": "esperado",
            "cargo": "N/D",
            "agency": "LACHMANN",
            "dwt": 0.0,
            "eta": eta,
            "raw": {f"c{i}": val[i] for i in range(len(val))},
        })
    return navios


# ---------------------------------------------------------------- Santos

def fetch_santos_atracacoes(timeout: int = 30) -> list:
    html = _fetch(SANTOS_ATRACACOES_URL, timeout=timeout)
    soup = BeautifulSoup(html, "html.parser")
    linhas = []
    for table in soup.select("table"):
        rows = table.select("tr")
        if not rows:
            continue
        # A tabela tem 2 linhas de cabeçalho: data/expedição e colunas trilíngues
        # ("NavioShipBurque", "CargaCargoCarga"). Localiza a linha com o IMO.
        header_idx = None
        for i, row in enumerate(rows[:4]):
            if any("IMO" in c.get_text().upper() for c in row.select("th, td")):
                header_idx = i
                break
        if header_idx is None:
            continue
        colunas = [c.get_text().strip() for c in rows[header_idx].select("th, td")]
        if not any("IMO" in c for c in colunas):
            continue
        # Normaliza cabeçalhos trilíngues: fica com o primeiro token da cadeia
        # (ex: "NavioShipBurque" -> "Navio") para podermos mapear por prefixo.
        def _normal(col, prefixos):
            for p in prefixos:
                for c in colunas:
                    if c.startswith(p):
                        return c
            return col

        for row in rows[header_idx + 1:]:
            valores = [c.get_text().strip() for c in row.select("td")]
            if len(valores) <= 1 or not valores[0]:
                continue
            reg = dict(zip(colunas, valores))
            imo = None
            imo_col = _normal(None, ["IMO"])
            if imo_col:
                imo_raw = reg.get(imo_col) or ""
                imo = re.sub(r"[^0-9]", "", imo_raw) or None
            vcol = _normal(None, ["Navio", "Nav"])
            vessel = (reg.get(vcol) if vcol else None) or "DESCONHECIDO"
            ccol = _normal(None, ["Carga", "Car"])
            cargo = normalizar_carga(reg.get(ccol) if ccol else None)
            ecol = _normal(None, ["ETA"])
            eta = reg.get(ecol) if ecol else None
            linhas.append({
                "port_id": "BRSSZ",
                "source": "santos",
                "vessel_name": str(vessel).upper(),
                "imo": imo,
                "status": "programado",
                "cargo": cargo,
                "agency": "NÃO CONFIRMADO",
                "dwt": 0.0,
                "eta": eta,
                "raw": reg,
            })
    return linhas


def fetch_santos_painel(timeout: int = 30) -> list:
    html = _fetch(SANTOS_PAINEL_URL, timeout=timeout)
    soup = BeautifulSoup(html, "html.parser")
    linhas = []
    for table in soup.select("table"):
        rows = table.select("tr")
        if not rows:
            continue
        header = [c.get_text().strip() for c in rows[0].select("th, td")]
        if "Navio" not in header:
            continue
        colunas = header
        for row in rows[1:]:
            valores = [c.get_text().strip() for c in row.select("td")]
            if len(valores) < len(colunas):
                continue
            reg = dict(zip(colunas, valores))
            vessel = (reg.get("Navio") or "DESCONHECIDO").upper()
            linhas.append({
                "port_id": "BRSSZ",
                "source": "santos_painel",
                "vessel_name": vessel,
                "imo": None,
                "status": "em_operacao",
                "cargo": normalizar_carga(reg.get("Carga")),
                "agency": (reg.get("Agente") or "NÃO CONFIRMADO").upper(),
                "dwt": 0.0,
                "eta": None,
                "raw": reg,
            })
    return linhas


# ---------------------------------------------------------------- orchestrator

def coletar_tudo(timeout: int = 30) -> dict:
    """Roda todos os coletores; isolamento de falha por fonte."""
    resultados = {
        "inicio": datetime.utcnow().isoformat(timespec="seconds"),
        "fontes": {},
        "total_rows": 0,
        "erros": [],
    }
    fontes = {
        "appa": appa_para_raw_rows,
        "lachmann": fetch_lachmann_schedule,
        "santos": fetch_santos_atracacoes,
        "santos_painel": fetch_santos_painel,
    }
    for nome, fn in fontes.items():
        try:
            rows = fn(timeout=timeout)
            resultados["fontes"][nome] = {"rows": len(rows), "ok": True}
            for r in rows:
                r["ingested_at"] = resultados["inicio"]
            resultados.setdefault("linhas", []).extend(rows)
            resultados["total_rows"] += len(rows)
        except Exception as e:
            resultados["fontes"][nome] = {"rows": 0, "ok": False, "erro": f"{type(e).__name__}: {e}"}
            resultados["erros"].append(f"{nome}: {e}")
    resultados.setdefault("linhas", [])
    return resultados


def resumo_por_porto(linhas: list) -> dict:
    """Deriva métricas de linha: total, status, ao_largo (fila de espera)."""
    from collections import Counter
    resumo = {}
    for r in linhas:
        pid = r["port_id"]
        s = resumo.setdefault(pid, Counter())
        s.update({"total": 1})
        status = TO_STATUS.get(r["status"], str(r["status"]).upper())
        s.update({"status_" + status: 1})
        s.update({f"src_{r['source']}": 1})
    return {
        pid: {k: v for k, v in c.items()}
        for pid, c in resumo.items()
    }


if __name__ == "__main__":
    import json
    import sys

    resultado = coletar_tudo()
    print("=== RESULTADO DA INGESTÃO ===")
    print("Fontes:", json.dumps(resultado["fontes"], indent=2, ensure_ascii=False))
    print("Total rows:", resultado["total_rows"])
    if resultado["erros"]:
        print("Erros:", resultado["erros"])
    print("\n=== RESUMO POR PORTO ===")
    print(json.dumps(resumo_por_porto(resultado.get("linhas", [])), indent=2, ensure_ascii=False))