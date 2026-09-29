"""Constrói o seed curado de produção (`seed/oracle_seed.duckdb`).

Por que existe: em produção o `data/` é um VOLUME persistente do Railway que
 sombreia o `data/` da imagem. O `init_prod_db` roda com o volume e, portanto,
nunca enxerga o banco commitado no repo — resultado histórico: prod nasceu só
com o esqueleto (port_metrics/port_metrics_history/freight_rates/tax_rules) e
SEM `antaq_validation` nem `calibration_pairs`, que são consumidos por
`risk_model.load_antaq_validation`, `control_tower` e `engine/calibration`.

Regras do seed (integridade comercial):
  - Só dado de REFERÊNCIA/HISTÓRICO aprovado.
  - Linhas `data_source LIKE 'live:%'` são EXCLUÍDAS: os sensores que as geravam
    (santospainel.com.br, web3.antaq.gov.br) saíram do ar, então ressuscitá-las
    faria o produto apresentar medição velha como leitura atual.
  - `_seed_manifest` registra proveniência (origem, sha256, regras, contagens).

Uso:
    python scripts/build_seed.py [--source data/oracle.duckdb] [--out seed/oracle_seed.duckdb]
"""
import argparse
import hashlib
import os
import shutil
import sys
from datetime import datetime, timezone

import duckdb

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Tabela -> chave natural usada para decidir o que já existe.
SEED_TABLES: dict[str, list[str]] = {
    "antaq_validation": ["port_id", "ano", "mes"],
    "calibration_pairs": ["port_id", "observed_at"],
    "port_metrics": ["port_id"],
    "port_metrics_history": ["port_id", "captured_at"],
}

# Tabelas onde linhas de sensor morto não podem entrar no seed.
NO_LIVE_TABLES = ("port_metrics", "port_metrics_history")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(source: str, out: str) -> int:
    if not os.path.exists(source):
        print(f"[SEED] ERRO: source inexistente: {source}")
        return 1

    src_sha = _sha256(source)
    built_at = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    for suffix in ("", ".wal"):
        if os.path.exists(out + suffix):
            os.remove(out + suffix)

    src = duckdb.connect(source, read_only=True)
    available = {
        r[0]
        for r in src.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
    }
    missing = [t for t in SEED_TABLES if t not in available]
    if missing:
        print(f"[SEED] ERRO: source sem tabelas obrigatórias: {missing}")
        src.close()
        return 1

    dst = duckdb.connect(out)
    counts: dict[str, int] = {}
    excluded_live: dict[str, int] = {}
    dst.execute(f"ATTACH '{source}' AS seed_src (READ_ONLY)")

    for table, keys in SEED_TABLES.items():
        cols = [r[0] for r in src.execute(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_name='{table}' ORDER BY ordinal_position"
        ).fetchall()]
        col_sql = ", ".join(f'"{c}"' for c in cols)
        where = ""
        if table in NO_LIVE_TABLES:
            n_live = src.execute(
                f"SELECT COUNT(*) FROM {table} WHERE data_source LIKE 'live:%'"
            ).fetchone()[0]
            excluded_live[table] = n_live
            where = " WHERE data_source NOT LIKE 'live:%'"
        # Cria a tabela com o mesmo esquema e popula a partir do source anexado.
        dst.execute(f"CREATE TABLE {table} AS SELECT {col_sql} FROM seed_src.{table}{where}")
        counts[table] = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"[SEED] {table:22s} linhas={counts[table]:5d} (live excluídas: {excluded_live.get(table, 0)})")

    dst.execute("DETACH seed_src")

    dst.execute(
        """
        CREATE TABLE _seed_manifest(
            built_at VARCHAR, source_path VARCHAR, source_sha256 VARCHAR,
            tables_json VARCHAR, excluded_live_json VARCHAR, rules VARCHAR
        )
        """
    )
    rules = (
        "Somente referencia/historico aprovado. Linhas data_source LIKE 'live:%' "
        "excluidas: sensores de origem (santospainel.com.br / web3.antaq.gov.br) "
        "sairam do ar (NXDOMAIN) e nao podem ser apresentadas como medicao atual. "
        "Hidratacao em producao e aditiva e idempotente (src/engine/seed_hydration.py)."
    )
    import json

    dst.execute(
        "INSERT INTO _seed_manifest VALUES (?,?,?,?,?,?)",
        [built_at, source, src_sha, json.dumps(counts), json.dumps(excluded_live), rules],
    )
    dst.close()
    src.close()

    out_sha = _sha256(out)
    print(f"[SEED] origem : {source}")
    print(f"[SEED] sha256 origem : {src_sha}")
    print(f"[SEED] gerado : {out} ({os.path.getsize(out)} bytes)")
    print(f"[SEED] sha256 seed   : {out_sha}")
    print(f"[SEED] built_at: {built_at}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="data/oracle.duckdb")
    ap.add_argument("--out", default="seed/oracle_seed.duckdb")
    raise SystemExit(build(ap.parse_args().source, ap.parse_args().out))
