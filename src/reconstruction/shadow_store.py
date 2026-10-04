import duckdb
import os
import threading
from typing import Dict, Any

class ShadowStore:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(ShadowStore, cls).__new__(cls)
                    cls._instance._init_store()
        return cls._instance
        
    def _init_store(self):
        self.metrics = {
            "orders_processed": 0,
            "new_evidence": 0,
            "deduplicated_evidence": 0,
            "new_entities": 0,
            "updated_entities": 0,
            "new_portcalls": 0,
            "updated_portcalls": 0,
            "new_shipments": 0,
            "updated_shipments": 0,
            "new_hypotheses": 0,
            "invalidated_hypotheses": 0,
            "contradictions": 0,
            "pipeline_failures": 0
        }
        
        # Datastores
        self.shipments = {}
        self.vessels = {}
        self.portcalls = {}
        self.evidences = {}
        
        db_path = os.getenv("SHADOW_DB_PATH", ":memory:") 
        self.conn = duckdb.connect(db_path)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS shadow_metrics (
                metric_name VARCHAR PRIMARY KEY,
                metric_value INTEGER
            )
        """)
        self._restore_metrics()

        # Ledger durável: compartilha a conexão do store para que evidências,
        # entidades, port calls e shipments sobrevivam além da instância.
        from src.reconstruction.persistence.repository import ReconstructionRepository
        self._repository = ReconstructionRepository(self.conn)

    @property
    def repository(self):
        # Leitura/escrita duráveis. O read surface importa ShadowStore (não a
        # referência do módulo) para enxergar o singleton rebindado em testes.
        return self._repository

    def _persist(self, fn, *args):
        # DuckDB: uma conexão não é thread-safe; serializa com o lock do store.
        with self._lock:
            return fn(*args)

    def persist_evidence(self, ev) -> str:
        return self._persist(self._repository.save_evidence, ev)

    def persist_vessel(self, vessel) -> None:
        self._persist(self._repository.save_vessel, vessel)

    def persist_port_call(self, pc) -> None:
        self._persist(self._repository.save_port_call, pc)

    def persist_shipment(self, shipment) -> None:
        self._persist(self._repository.save_shipment, shipment)

    def load_shipment(self, stable_id):
        with self._lock:
            return self._repository.load_shipment(stable_id)

    def _restore_metrics(self):
        # Contadores sobrevivem a restart somente com SHADOW_DB_PATH real;
        # ":memory:" é por instância e recomeça zerado.
        if os.getenv("SHADOW_DB_PATH", ":memory:") == ":memory:":
            return
        try:
            rows = self.conn.execute(
                "SELECT metric_name, metric_value FROM shadow_metrics"
            ).fetchall()
            for name, value in rows:
                if name in self.metrics:
                    self.metrics[name] = int(value)
        except Exception:
            pass
        
    def increment(self, metric: str, count: int = 1):
        with self._lock:
            if metric in self.metrics:
                self.metrics[metric] += count
            self.conn.execute(
                "INSERT INTO shadow_metrics (metric_name, metric_value) VALUES (?, ?) ON CONFLICT (metric_name) DO UPDATE SET metric_value = metric_value + ?", 
                (metric, self.metrics.get(metric, 1), count)
            )

    def get_metrics(self) -> Dict[str, int]:
        with self._lock:
            return dict(self.metrics)

    def reset_state(self):
        # For testing
        with self._lock:
            for k in self.metrics:
                self.metrics[k] = 0
            self.shipments.clear()
            self.vessels.clear()
            self.portcalls.clear()
            self.evidences.clear()
            # O store agora possui o ledger durável: resetar sem limpá-lo
            # deixaria evidências antigas deduplicando cargas novas. A guarda
            # :memory: impede que este hook de teste apague um banco real.
            if os.getenv("SHADOW_DB_PATH", ":memory:") == ":memory:":
                for table in (
                    "evidence_ledger",
                    "shipment_reconstructions",
                    "entities_vessel",
                    "entities_port_call",
                ):
                    self.conn.execute(f"DELETE FROM {table}")
            
shadow_store = ShadowStore()
