import os
import duckdb

from dotenv import load_dotenv

load_dotenv("config/.env")
RAW_DB = os.getenv("RAW_DATABASE_PATH", "data/processed/aether_oracle.duckdb")

def get_verified_cargo_queue(port_id: str) -> dict:
    """
    Constrói um sinal verificado da fila de cargas.
    Retorna o total de navios AO_LARGO e sua distribuição por carga.
    Aborta (INSUFFICIENT_OBSERVATION) se o porto não possui dados vivos reais.
    """
    port_id = port_id.upper()
    
    if not os.path.exists(RAW_DB):
        return _insufficient_observation(port_id, "Raw database not found.")
        
    try:
        conn = duckdb.connect(RAW_DB, read_only=True)
    except duckdb.Error:
        return _insufficient_observation(port_id, "Could not connect to raw database.")
        
    try:
        total_rows = conn.execute(
            "SELECT COUNT(*) FROM raw_port_lineup WHERE port_id = ?", [port_id]
        ).fetchone()[0]
        
        if total_rows == 0:
            return _insufficient_observation(port_id, f"No verified live line-up observation for {port_id}.")
            
        # Pega a fila real ancorada
        ships = conn.execute(
            """
            SELECT vessel_name, cargo, dwt, ingested_at, source
            FROM raw_port_lineup
            WHERE port_id = ? AND status = 'AO_LARGO'
            ORDER BY vessel_name
            """, [port_id]
        ).fetchall()
        
        last_ingested_row = conn.execute(
            "SELECT MAX(CAST(ingested_at AS VARCHAR)) FROM raw_port_lineup WHERE port_id = ?", [port_id]
        ).fetchone()
        last_ingested = last_ingested_row[0] if last_ingested_row else None
        
        cargo_distribution = {}
        total_dwt = 0.0
        sources_found = set()
        for name, cargo, dwt, ingested, src in ships:
            if src:
                sources_found.add(src)
            cargo_norm = str(cargo).strip().upper()
            if not cargo_norm or cargo_norm == 'NONE':
                cargo_norm = "DESCONHECIDA"
            cargo_distribution[cargo_norm] = cargo_distribution.get(cargo_norm, 0) + 1
            total_dwt += (dwt or 0.0)
            
        waiting_vessels = len(ships)
        
        # Pega a fila ferroviária (Land Operations)
        try:
            land_rows = conn.execute(
                """
                SELECT train_id, terminal, commodity, wagons, status, source 
                FROM raw_land_queue 
                WHERE port_id = ?
                """, [port_id]
            ).fetchall()
            
            land_operations = {}
            total_wagons = 0
            for t_id, term, comm, wag, st, src in land_rows:
                if src:
                    sources_found.add(src)
                total_wagons += wag
                if term not in land_operations:
                    land_operations[term] = {"wagons": 0, "trains": 0}
                land_operations[term]["wagons"] += wag
                land_operations[term]["trains"] += 1
                
        except duckdb.Error:
            land_operations = {}
            total_wagons = 0
            
    finally:
        conn.close()
        
    # Choque de Oferta Terrestre (Land-Side Pressure)
    # Se navios baixos, mas vagões altos => gargalo logístico interno
    if waiting_vessels >= 12 or total_wagons > 100:
        pressure_level = "ELEVATED"
    elif waiting_vessels < 4 and total_wagons < 50:
        pressure_level = "LOW"
    else:
        pressure_level = "MODERATE"
        
    evidence_text = f"Verified {waiting_vessels} vessels anchored ('AO_LARGO'). "
    if total_wagons > 0:
        evidence_text += f"Land-side congestion detected: {total_wagons} wagons inbound/waiting. "
        
    if cargo_distribution:
        top_cargos = sorted(cargo_distribution.items(), key=lambda x: x[1], reverse=True)
        evidence_text += "Sea Cargo breakdown: " + ", ".join(f"{count} {c}" for c, count in top_cargos) + "."
    else:
        evidence_text += "No vessels waiting."

    return {
        "port_id": port_id,
        "signal": "VERIFIED_MULTIMODAL_OBSERVATION",
        "pressure_level": pressure_level,
        "waiting_vessels": waiting_vessels,
        "cargo_distribution": cargo_distribution,
        "total_waiting_dwt": total_dwt,
        "land_operations": land_operations,
        "total_wagons_waiting": total_wagons,
        "evidence": evidence_text,
        "sources": sorted(list(sources_found)),
        "as_of": last_ingested,
    }

def _insufficient_observation(port_id: str, reason: str) -> dict:
    return {
        "port_id": port_id,
        "signal": "INSUFFICIENT_OBSERVATION",
        "pressure_level": "UNKNOWN",
        "waiting_vessels": 0,
        "cargo_distribution": {},
        "total_waiting_dwt": 0.0,
        "land_operations": {},
        "total_wagons_waiting": 0,
        "evidence": reason,
        "sources": [],
        "as_of": None,
    }
