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
            
shadow_store = ShadowStore()
