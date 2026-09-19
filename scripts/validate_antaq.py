"""Camada de validação ANTAQ (ground-truth tardio) — moat de confiabilidade.

Baixa/cacheia o espelho do Estatístico Aquaviário (atracação + tempos) via
HuggingFace (fonte oficial estatistica.antaq.gov.br está atrás de Cloudflare),
agrega por porto/mês e grava em `antaq_validation` no DuckDB de produção:

    port_id, ano, mes, n_atracacoes, n_com_imo, espera_atracacao_h_avg,
    espera_atracacao_h_med, espera_atracacao_h_p90, atracado_h_avg,
    estadia_h_avg, gerado_em

Isso permite comparar retrospectivamente o sinal do oráculo (congestion_score /
eta_delay_days) com o que a ANTAQ registrou de fato (espera real de atracação),
a base de "10 portos bem observados com validação" definida como prioridade.

Uso:
    python scripts/validate_antaq.py [--refresh] [--test]
        --refresh  obriga re-download do parquet (default: usa cache < 90d)
        --test     mostra a agregação sem gravar
"""

import argparse
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

import duckdb
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

HF_BASE = "https://huggingface.co/datasets/vinicius-souza/antaq/resolve/main/gold"
FILES = {
    "atracacao": f"{HF_BASE}/atracacao_master.parquet",
    "ocupacao": f"{HF_BASE}/taxa_ocupacao_anual.parquet",
}
CACHE_DIR = os.getenv("ANTAQ_CACHE_DIR", "data/antaq_cache")


def load_env():
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.getcwd(), "config", ".env"))


def db_path() -> str:
    return os.getenv("DATABASE_PATH", "data/oracle.duckdb")


def slugify(name: str) -> str:
    """Normaliza nomes de complexo/porto p/ comparação insensível a acento."""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", text.lower().strip())


# Mapeamento Complexo Portuário ANTAQ -> port_id do oráculo.
# Niterói e Rio dividem o mesmo complexo; a separação é por terminal no join.
COMPLEXO_TO_PORT = {
    "santos": "BRSSZ",
    "paranagua_antonina": "BRPNG",
    "itanhae_antonina": "BRPNG",
    "itaguai": "BRITG",
}
# Terminais da Baía de Guanabara que pertencem a Niterói (margem leste).
NITEROI_TERMINALS = re.compile(
    r"niter|renave|mac_laren|briclog|wellstream|brasco|utc_engenharia|"
    r"maua|ilha_do_governador|camorim|ilha_redonda|subsea|ponte_do_thun|"
    r"gnl_da_baia|cosan_lubrif|braskem", re.I
)


def ensure_cache() -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR


def fetch_antaq(path: str, force: bool = False) -> dict[str, str]:
    """Baixa os parquets (se faltarem ou estiverem velhos >90d) e retorna caminhos."""
    import urllib.request

    ensure_cache()
    local = {}
    for key, url in FILES.items():
        dest = os.path.join(CACHE_DIR, f"{key}.parquet")
        need = force
        if os.path.exists(dest):
            age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(dest))).days
            need = force or age > 90
        else:
            need = True
        if need:
            print(f"[ANTAQ] baixando {key}: {url}")
            urllib.request.urlretrieve(url, dest)
        local[key] = dest
    return local


def _mojibake_fix(name: object) -> str:
    """Para colunas lidas do parquet com acentos corrompidos (latin1->utf8)."""
    s = str(name)
    try:
        return s.encode("latin-1").decode("utf-8")
    except Exception:
        return s


def map_port(complejo: object, terminal: object) -> str | None:
    comp = slugify(_mojibake_fix(complejo))
    port = COMPLEXO_TO_PORT.get(comp)
    if port != "BRSSZ" and comp.startswith("rio_de_janeiro"):
        ter = slugify(_mojibake_fix(terminal))
        return "BRNIT" if "niteroi" in ter or NITEROI_TERMINALS.search(ter) else "BRRIO"
    return port


def build_monthly(paths: dict[str, str]) -> pd.DataFrame:
    """Agrega atracações por porto/mês (2023+), com métricas de espera real."""
    cols = [
        "Complexo Portuário", "Porto Atracação", "Ano", "Mes",
        "Data Atracação", "Nº do IMO", "TEsperaAtracacao", "TAtracado", "TEstadia",
    ]
    df = pd.read_parquet(paths["atracacao"], columns=cols)
    df = df[df["Ano"] >= 2023].copy()

    df["port_id"] = df.apply(lambda r: map_port(r["Complexo Portuário"], r["Porto Atracação"]), axis=1)
    df = df[df["port_id"].notna()].copy()

    df["espera_h"] = df["TEsperaAtracacao"]
    df["atracado_h"] = df["TAtracado"]
    df["estadia_h"] = df["TEstadia"]

    for c in ("espera_h", "atracado_h", "estadia_h"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    g = df.groupby(["port_id", "Ano", "Mes"])
    out = pd.DataFrame({
        "n_atracacoes": g.size(),
        "n_com_imo": g["Nº do IMO"].apply(lambda s: s.notna().sum()),
        "espera_atracacao_h_avg": g["espera_h"].mean(),
        "espera_atracacao_h_med": g["espera_h"].median(),
        "espera_atracacao_h_p90": g["espera_h"].quantile(0.90),
        "atracado_h_avg": g["atracado_h"].mean(),
        "estadia_h_avg": g["estadia_h"].mean(),
    }).reset_index()

    out["espera_atracacao_h_med"] = out["espera_atracacao_h_med"].fillna(out["espera_atracacao_h_avg"])
    out["espera_atracacao_h_p90"] = out["espera_atracacao_h_p90"].fillna(out["espera_atracacao_h_avg"])
    return out


def write_validations(conn, monthly: pd.DataFrame) -> int:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS antaq_validation (
            port_id VARCHAR,
            ano INTEGER,
            mes VARCHAR,
            n_atracacoes INTEGER,
            n_com_imo INTEGER,
            espera_atracacao_h_avg DOUBLE,
            espera_atracacao_h_med DOUBLE,
            espera_atracacao_h_p90 DOUBLE,
            atracado_h_avg DOUBLE,
            estadia_h_avg DOUBLE,
            gerado_em TIMESTAMP
        )
    """)
    conn.execute("DELETE FROM antaq_validation")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = monthly.copy()
    rows["gerado_em"] = now
    conn.executemany(
        """
        INSERT INTO antaq_validation (
            port_id, ano, mes, n_atracacoes, n_com_imo,
            espera_atracacao_h_avg, espera_atracacao_h_med, espera_atracacao_h_p90,
            atracado_h_avg, estadia_h_avg, gerado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows[["port_id", "Ano", "Mes", "n_atracacoes", "n_com_imo",
              "espera_atracacao_h_avg", "espera_atracacao_h_med",
              "espera_atracacao_h_p90", "atracado_h_avg", "estadia_h_avg", "gerado_em"]].values.tolist(),
    )
    return len(rows)


def summarize(monthly: pd.DataFrame) -> str:
    lines = []
    for pid in sorted(monthly["port_id"].unique()):
        sub = monthly[monthly["port_id"] == pid]
        recent = sub[sub["Ano"] == sub["Ano"].max()]
        avg = recent["espera_atracacao_h_avg"].mean()
        lines.append(
            f"  {pid}: {recent['n_atracacoes'].sum()} atracacoes (ultima janela), "
            f"espera media ~{avg:.1f}h, p90 ~{recent['espera_atracacao_h_p90'].mean():.0f}h"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Re-baixa os parquets")
    parser.add_argument("--test", action="store_true", help="Não grava, só mostra")
    args = parser.parse_args()

    load_env()
    paths = fetch_antaq(db_path(), force=args.refresh)
    monthly = build_monthly(paths)

    print(f"[ANTAQ] agregação mensal: {len(monthly)} linhas")
    print(summarize(monthly))

    if args.test:
        print("[ANTAQ] --test: nada gravado")
        return 0

    conn = duckdb.connect(db_path())
    try:
        n = write_validations(conn, monthly)
        print(f"[ANTAQ] validacao gravada: {n} linhas em {db_path()}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())