import pytest
import duckdb
import os
import tempfile
import json
import collections
from pathlib import Path

# 1. Fallback silencioso
def test_no_fallback_to_production_db(monkeypatch):
    import src.engine.risk_model
    import scripts.run_ingestion_live
    import importlib
    
    invalid_path = "/tmp/does_not_exist_aetherx.duckdb"
    monkeypatch.setenv("DATABASE_PATH", invalid_path)
    monkeypatch.setenv("AETHERX_ALLOW_DB_CREATION", "0")
    
    # risk_model tests runtime failure
    with pytest.raises(RuntimeError, match="Configured DATABASE_PATH does not exist and DB creation not allowed"):
        importlib.reload(src.engine.risk_model)

    with pytest.raises(RuntimeError, match="Configured DATABASE_PATH does not exist"):
        importlib.reload(scripts.run_ingestion_live)

# 2. Impedimento de escrita no banco operacional
def test_duckdb_write_protection():
    with pytest.raises(RuntimeError, match="TEST ISOLATION BREACH"):
        duckdb.connect("data/oracle.duckdb")
        
    with pytest.raises(RuntimeError, match="TEST ISOLATION BREACH"):
        duckdb.connect(Path("data/oracle.duckdb"))

# 3. Nenhuma ingestao real inicializada
def test_no_live_ingestion_started():
    import os
    assert os.getenv("ENABLE_LIVE_INGESTION") == "0"
    
# 4. _load_state idempotency
def test_load_state_idempotency(tmp_path, monkeypatch):
    import src.api.metrics as metrics
    import copy
    
    state_file = tmp_path / "metrics_state.json"
    monkeypatch.setattr(metrics, "_STATE_PATH", str(state_file))
    
    with metrics._lock:
        metrics._counts.clear()
        metrics._counts.update({"api_calls": 5})
        metrics._MACHINE_TOOL_NAMES.clear()
        metrics._MACHINE_TOOL_NAMES.setdefault("machine_1", collections.Counter())["tool_A"] = 3
        metrics._tool_errors.clear()
        metrics._tool_errors.append("error_1")
    
    metrics._persist_now()
    metrics._load_state()
    assert metrics._counts["api_calls"] == 5
    assert metrics._MACHINE_TOOL_NAMES["machine_1"]["tool_A"] == 3
    assert list(metrics._tool_errors) == ["error_1"]
    
    metrics._load_state()
    assert metrics._counts["api_calls"] == 5
    assert metrics._MACHINE_TOOL_NAMES["machine_1"]["tool_A"] == 3
    assert len(list(metrics._tool_errors)) == 1

# 5. Snapshot invalido preserva estado atual
def test_load_state_invalid_json(tmp_path, monkeypatch):
    import src.api.metrics as metrics
    
    state_file = tmp_path / "metrics_state.json"
    monkeypatch.setattr(metrics, "_STATE_PATH", str(state_file))
    
    metrics._counts.clear()
    metrics._counts.update({"api_calls": 10})
    
    state_file.write_text("{invalid_json:")
    metrics._load_state()
    
    assert metrics._counts["api_calls"] == 10

# 6. Snapshot incompleto preserva chaves nao presentes e last_tool_call
def test_load_state_incomplete_snapshot_preserves_state(tmp_path, monkeypatch):
    import src.api.metrics as metrics
    
    state_file = tmp_path / "metrics_state.json"
    monkeypatch.setattr(metrics, "_STATE_PATH", str(state_file))
    
    metrics._uniq.clear()
    metrics._uniq["ip"] = {"1.1.1.1"}
    metrics._counts.clear()
    metrics._counts["api_calls"] = 5
    metrics._last_tool_call = "preserve_me"
    
    # Write incomplete state (only counts, no uniq, no last_tool_call)
    state_file.write_text(json.dumps({"counts": {"api_calls": 2}}))
    metrics._load_state()
    
    assert metrics._counts["api_calls"] == 2
    assert "ip" in metrics._uniq
    assert "1.1.1.1" in metrics._uniq["ip"]
    assert metrics._last_tool_call == "preserve_me"

def test_load_state_valid_json_invalid_types_preserves_state(tmp_path, monkeypatch):
    import src.api.metrics as metrics
    import json
    
    state_file = tmp_path / "metrics_state.json"
    monkeypatch.setattr(metrics, "_STATE_PATH", str(state_file))
    
    metrics._counts.clear()
    metrics._counts.update({"api_calls": 10})
    metrics._uniq.clear()
    metrics._uniq["ip"] = {"1.1.1.1"}
    
    # Valid JSON but invalid types (string instead of dict)
    state_file.write_text(json.dumps({
        "counts": {"api_calls": 2}, # This would succeed
        "uniq": "this is not a dict" # This will throw ValueError when dict() or items() is called
    }))
    
    metrics._load_state()
    
    # The whole update should be aborted atomically, so counts is still 10, not 2
    assert metrics._counts["api_calls"] == 10
    assert "1.1.1.1" in metrics._uniq["ip"]

def test_load_state_valid_json_invalid_types_preserves_state(tmp_path, monkeypatch):
    import src.api.metrics as metrics
    import json
    
    state_file = tmp_path / "metrics_state.json"
    monkeypatch.setattr(metrics, "_STATE_PATH", str(state_file))
    
    metrics._counts.clear()
    metrics._counts.update({"api_calls": 10})
    metrics._uniq.clear()
    metrics._uniq["ip"] = {"1.1.1.1"}
    
    # Valid JSON but invalid types (string instead of dict)
    state_file.write_text(json.dumps({
        "counts": {"api_calls": 2}, # This would succeed
        "uniq": "this is not a dict" # This will throw ValueError when dict() or items() is called
    }))
    
    metrics._load_state()
    
    # The whole update should be aborted atomically, so counts is still 10, not 2
    assert metrics._counts["api_calls"] == 10
    assert "1.1.1.1" in metrics._uniq["ip"]
