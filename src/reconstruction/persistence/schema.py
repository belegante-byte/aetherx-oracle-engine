import duckdb

def create_schema(conn: duckdb.DuckDBPyConnection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS evidence_ledger (
        logical_id VARCHAR PRIMARY KEY,
        evidence_id VARCHAR,
        source VARCHAR,
        claim_field VARCHAR,
        claim_value JSON,
        epistemic_state VARCHAR,
        confidence DOUBLE,
        entity JSON,
        source_observed_at VARCHAR,
        retrieved_at VARCHAR,
        origin_order_id VARCHAR,
        created_at TIMESTAMP,
        is_tombstone BOOLEAN DEFAULT FALSE,
        target_logical_id VARCHAR
    );
    
    CREATE TABLE IF NOT EXISTS entities_vessel (
        stable_id VARCHAR PRIMARY KEY,
        payload JSON
    );
    
    CREATE TABLE IF NOT EXISTS entities_voyage (
        stable_id VARCHAR PRIMARY KEY,
        payload JSON
    );
    
    CREATE TABLE IF NOT EXISTS entities_port_call (
        stable_id VARCHAR PRIMARY KEY,
        payload JSON
    );
    
    CREATE TABLE IF NOT EXISTS shipment_reconstructions (
        stable_id VARCHAR PRIMARY KEY,
        port_call_id VARCHAR,
        payload JSON
    );
    
    CREATE TABLE IF NOT EXISTS operational_orders (
        order_id VARCHAR PRIMARY KEY,
        payload JSON
    );
    """)
