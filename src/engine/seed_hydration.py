"""Hidrata o banco de produção a partir do seed curado (`seed/oracle_seed.duckdb`).

Contexto (bug de infraestrutura, 2026-09-29): em produção `data/` é um VOLUME
persistente do Railway que SOMBREIA o `data/` da imagem. O bootstrap
(`init_prod_db`) rodava contra o volume e criava apenas o esqueleto, então
`antaq_validation` (185 linhas) e `calibration_pairs` (6) — consumidos por
`risk_model.load_antaq_validation`, `control_tower` e `engine/calibration` —
nunca existiram em produção. O seed vive fora de `data/` justamente para não ser
sombreado pelo volume.

Garantias (esta é a parte que não se negocia):
  1. ADITIVO apenas: nunca DROP, nunca DELETE, nunca UPDATE de linha existente.
  2. Insere SOMENTE o que falta, por chave natural → reexecutar não duplica.
  3. Nunca sobrescreve observação existente (preserva a mais recente).
  4. Linhas de sensor morto (`data_source LIKE 'live:%'`) nunca são hidratadas
     nem mesmo que estejam no seed: apresentá-las seria mostrar medição velha
     como leitura atual.
  5. Se a tabela alvo existir com menos colunas, adiciona as que faltam
     (ALTER TABLE ADD COLUMN, aditivo) e hidrata a interseção; se faltar coluna
     no seed, registra e segue — nunca destrói schema.
  6. Cada execução vira uma linha em `seed_hydration_log` (auditoria +
     prova de idempotência: contagens por tabela + sha256 do seed).
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

import duckdb

# Tabela -> chave natural. Mesma definição usada por scripts/build_seed.py.
SEED_TABLES: dict[str, list[str]] = {
    "antaq_validation": ["port_id", "ano", "mes"],
    "calibration_pairs": ["port_id", "observed_at"],
    "port_metrics": ["port_id"],
    "port_metrics_history": ["port_id", "captured_at"],
}

NO_LIVE_TABLES = ("port_metrics", "port_metrics_history")

LOG_TABLE = "seed_hydration_log"
_ALIAS = "seed_src"


def default_seed_path() -> str:
    """Caminho do seed: `SEED_DB_PATH` > raiz do repo > cwd.

    Não confiar no cwd: em produção o start command roda de `/app`, mas um
    processo iniciado de outro diretório não encontraria o artefato e a
    hidratação viraria no-op silencioso.
    """
    env = os.getenv("SEED_DB_PATH")
    if env:
        return env
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    anchored = os.path.join(root, "seed", "oracle_seed.duckdb")
    if os.path.exists(anchored):
        return anchored
    return os.path.join("seed", "oracle_seed.duckdb")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _db_name(conn, database: str) -> str:
    """`main` é o SCHEMA; em DB de arquivo o database tem o nome do arquivo."""
    if database != "main":
        return database
    return conn.execute("SELECT current_database()").fetchone()[0]


def _tables(conn, database: str = "main") -> set[str]:
    """Tabelas de um database do catálogo.

    NÃO usar information_schema aqui: no DuckDB ele só descreve o database
    corrente e chega a listar tabelas de um DB anexado como se fossem de `main`
    (o que faria a crer errado que antaq_validation já existe).
    """
    return {
        r[0]
        for r in conn.execute(
            "SELECT table_name FROM duckdb_tables() "
            "WHERE database_name = ? AND schema_name = 'main'",
            [_db_name(conn, database)],
        ).fetchall()
    }


def _columns(conn, table: str, database: str = "main") -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM duckdb_columns() "
            "WHERE database_name = ? AND schema_name = 'main' AND table_name = ? "
            "ORDER BY column_index",
            [_db_name(conn, database), table],
        ).fetchall()
    ]


def _column_types(conn, table: str, database: str = "main") -> dict[str, str]:
    return {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT column_name, data_type FROM duckdb_columns() "
            "WHERE database_name = ? AND schema_name = 'main' AND table_name = ?",
            [_db_name(conn, database), table],
        ).fetchall()
    }


def _ensure_log_table(conn) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {LOG_TABLE}(
            run_id VARCHAR, ran_at VARCHAR, seed_path VARCHAR, seed_sha256 VARCHAR,
            seed_built_at VARCHAR, status VARCHAR, report_json VARCHAR
        )
        """
    )


def _record(conn, seed_path: str, seed_sha: str, status: str, report: dict) -> None:
    conn.execute(
        f"INSERT INTO {LOG_TABLE} VALUES (?,?,?,?,?,?,?)",
        [
            f"run_{uuid.uuid4().hex[:12]}",
            datetime.now(timezone.utc).isoformat(),
            seed_path,
            seed_sha,
            report.get("seed_built_at", ""),
            status,
            json.dumps(report, ensure_ascii=False),
        ],
    )


def hydrate_from_seed(
    conn,
    seed_path: str | None = None,
    *,
    strict_live_filter: bool = True,
) -> dict:
    """Hidrata aditivamente a partir do seed. Retorna relatório (também logado).

    Nunca levanta por falta de seed: um seed ausente é registrado como
    `skipped_no_seed` e o banco segue como está (o bootstrap nunca deve derrubar
    a API por falta de artefato).
    """
    seed_path = seed_path or default_seed_path()
    _ensure_log_table(conn)

    if not os.path.exists(seed_path):
        report = {"status": "skipped_no_seed", "seed_path": seed_path, "inserted": {}, "added_columns": {}}
        _record(conn, seed_path, "", "skipped_no_seed", report)
        return report

    seed_sha = _sha256(seed_path)
    report: dict = {
        "status": "ok",
        "seed_path": seed_path,
        "seed_sha256": seed_sha,
        "inserted": {},
        "already_present": {},
        "added_columns": {},
        "skipped_columns": {},
        "live_rows_blocked": {},
        "seed_built_at": "",
    }

    conn.execute(f"ATTACH '{seed_path}' AS {_ALIAS} (READ_ONLY)")
    try:
        manifest = None
        if "_seed_manifest" in _tables(conn, _ALIAS):
            manifest = conn.execute(
                f"SELECT built_at, tables_json, excluded_live_json FROM {_ALIAS}._seed_manifest "
                "ORDER BY built_at DESC LIMIT 1"
            ).fetchone()
            report["seed_built_at"] = manifest[0] or ""
            report["seed_declared_tables"] = json.loads(manifest[1]) if manifest[1] else {}
            report["seed_excluded_live"] = json.loads(manifest[2]) if manifest[2] else {}

        main_tables = _tables(conn, "main")

        for table, keys in SEED_TABLES.items():
            if table not in _tables(conn, _ALIAS):
                continue
            seed_cols = _columns(conn, table, _ALIAS)
            if not seed_cols:
                continue

            # 4) Sensor morto nunca entra, mesmo que exista no seed — vale
            #    TANTO no caminho de criação quanto no de inserção.
            where = ""
            if strict_live_filter and table in NO_LIVE_TABLES and "data_source" in seed_cols:
                blocked = conn.execute(
                    f"SELECT COUNT(*) FROM {_ALIAS}.{table} WHERE data_source LIKE 'live:%'"
                ).fetchone()[0]
                if blocked:
                    report["live_rows_blocked"][table] = blocked
                where = " WHERE data_source NOT LIKE 'live:%'"

            if table not in main_tables:
                # Tabela ausente: cria com o esquema do seed e popula.
                if table in _tables(conn, "main"):
                    main_tables.add(table)
                else:
                    col_sql = ", ".join(f'"{c}"' for c in seed_cols)
                    conn.execute(
                        f"CREATE TABLE {table} AS SELECT {col_sql} FROM {_ALIAS}.{table}{where}"
                    )
                    main_tables.add(table)
                    report["inserted"][table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    report["already_present"][table] = 0
                    continue

            target_cols = _columns(conn, table, "main")
            # 5) Migração aditiva: adiciona colunas que faltam, nunca remove.
            #    DuckDB >=1.4 exige o TIPO em ADD COLUMN — usa o do seed.
            seed_types = _column_types(conn, table, _ALIAS)
            added = [c for c in seed_cols if c not in target_cols]
            for col in added:
                try:
                    conn.execute(
                        f'ALTER TABLE {table} ADD COLUMN "{col}" {seed_types.get(col, "VARCHAR")}'
                    )
                    report["added_columns"].setdefault(table, []).append(col)
                except Exception as exc:
                    report["skipped_columns"].setdefault(table, []).append(col)
                    report.setdefault("column_errors", {})[f"{table}.{col}"] = (
                        f"{type(exc).__name__}: {exc}"
                    )
            target_cols = _columns(conn, table, "main")
            shared = [c for c in seed_cols if c in target_cols]
            if not shared:
                continue
            skipped = [c for c in seed_cols if c not in shared]
            if skipped:
                current = report["skipped_columns"].setdefault(table, [])
                current.extend(c for c in skipped if c not in current)

            key_cols = [k for k in keys if k in shared]
            if not key_cols:
                continue

            join = " AND ".join(f"t.{k} IS NOT DISTINCT FROM s.{k}" for k in key_cols)
            col_sql = ", ".join(f'"{c}"' for c in shared)
            filtered = f"(SELECT * FROM {_ALIAS}.{table}{where}) s"
            total_src = conn.execute(f"SELECT COUNT(*) FROM {filtered}").fetchone()[0]
            missing = conn.execute(
                f"SELECT COUNT(*) FROM {filtered} "
                f"WHERE NOT EXISTS (SELECT 1 FROM {table} t WHERE {join})"
            ).fetchone()[0]
            report["already_present"][table] = max(0, total_src - missing)
            if missing:
                conn.execute(
                    f"INSERT INTO {table} ({col_sql}) "
                    f"SELECT {col_sql} FROM {filtered} "
                    f"WHERE NOT EXISTS (SELECT 1 FROM {table} t WHERE {join})"
                )
            report["inserted"][table] = missing

        # Contagem final (evidência antes/depois por execução).
        report["final_counts"] = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in SEED_TABLES
            if t in _tables(conn, "main")
        }
        _record(conn, seed_path, seed_sha, "ok", report)
    except Exception as exc:  # pragma: no cover - defensivo
        report["status"] = "error"
        report["error"] = f"{type(exc).__name__}: {exc}"
        try:
            _record(conn, seed_path, seed_sha, "error", report)
        except Exception:
            pass
        raise
    finally:
        try:
            conn.execute(f"DETACH {_ALIAS}")
        except Exception:
            pass
    return report
