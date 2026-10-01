import os
import tempfile
import shutil
import atexit
import pytest
import duckdb

# 1. Disable live ingestion and background tasks globally before FastAPI imports
os.environ["ENABLE_LIVE_INGESTION"] = "0"
os.environ["LIVE_INGESTION_INTERVAL_S"] = "999999"
os.environ.setdefault("RAPIDAPI_PROXY_SECRET", "test-secret")

# 2. Setup disposable DB with session lifecycle
_temp_dir = tempfile.mkdtemp()
_disposable_db = os.path.join(_temp_dir, "test_disposable_oracle.duckdb")

os.environ["DATABASE_PATH"] = _disposable_db
os.environ["RAW_DATABASE_PATH"] = _disposable_db
os.environ["AETHERX_ALLOW_DB_CREATION"] = "1"

# 3. DuckDB wrapper to block operational DB access EARLY
_original_connect = duckdb.connect

def safe_connect(database, *args, **kwargs):
    import tempfile
    if hasattr(database, "__fspath__"):
        db_path = database.__fspath__()
    else:
        db_path = str(database)

    allowed = False
    if db_path == ":memory:":
        allowed = True
    elif "test_disposable" in db_path:
        allowed = True
    elif tempfile.gettempdir() in db_path or "/tmp/pytest" in db_path or "pytest-of-" in db_path:
        allowed = True
    elif "seed/oracle_seed.duckdb" in db_path or "seed.duckdb" in db_path:
        allowed = True

    if not allowed:
        raise RuntimeError(f"TEST ISOLATION BREACH: Attempted to connect to operational DB: {db_path}")

    return _original_connect(database, *args, **kwargs)

duckdb.connect = safe_connect


# 4. Initialize fresh schema with safe_connect active
try:
    from src.engine.init_prod_db import seed_port_metrics
    seed_port_metrics(force=False)

    # INJECT CONTROLLED TEST DATA
    conn = duckdb.connect(_disposable_db)
    try:
        # Injetar BRPNG e BRSSZ como live (test_tier_restrictions exige isso)
        conn.execute("""
            UPDATE port_metrics SET data_source = 'live:mock', live_detail = '{"ao_largo": 1, "atracados": 2}', waiting_vessels = 1
            WHERE port_id IN ('BRPNG', 'BRSSZ', 'BRRIO', 'BRNIT', 'BRITG')
        """)

        # O oracle_seed ja criou a tabela port_metrics_history com 11 colunas.
        # Vamos usar INSERT com nomes explicitos
        conn.execute("""
            INSERT INTO port_metrics_history (port_id, captured_at, congestion_score, eta_delay_days, waiting_vessels, freight_volatility_index, data_source)
            VALUES
            ('BRSSZ', CURRENT_TIMESTAMP - INTERVAL '1 DAY', 0.8, 1.0, 10, 0.5, 'test:mock'),
            ('BRPNG', CURRENT_TIMESTAMP - INTERVAL '1 DAY', 0.6, 1.0, 5, 0.5, 'test:mock')
        """)

        # O verified-queue procura na tabela raw_port_lineup
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_port_lineup (
                port_id VARCHAR,
                vessel_name VARCHAR,
                imo VARCHAR,
                status VARCHAR,
                cargo VARCHAR,
                dwt DOUBLE,
                eta TIMESTAMP
            )
        """)
    finally:
        conn.close()

except Exception as e:
    raise RuntimeError(f"[CONFTEST] Fatal error initializing disposable DB: {e}") from e


# Cleanup on exit
def cleanup():
    shutil.rmtree(_temp_dir, ignore_errors=True)
atexit.register(cleanup)

"""Fixtures compartilhadas da suíte."""
from starlette.testclient import TestClient

@pytest.fixture(scope="session")
def mcp_client():
    from src.api.main import app
    with TestClient(app) as c:
        yield c
