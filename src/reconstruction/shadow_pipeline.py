import uuid
import logging
from typing import Dict, Any
from datetime import datetime, timezone

from src.reconstruction.models import OperationalOrder, ShipmentReconstruction, IdentityState, EpistemicState
from src.reconstruction.extractor import OrderExtractor
from src.reconstruction.engine import ReconstructionEngine
from src.reconstruction.resolver import EntityResolver
from src.reconstruction.hypothesis_engine import HypothesisEngine
from src.reconstruction.shadow_store import shadow_store

logger = logging.getLogger(__name__)

def run_shadow_pipeline(port_id: str, objective: str, mcp_result: Dict[str, Any]):
    """
    Executes Phase 4A/4B Shadow Pipeline synchronously but isolated via try-except.
    Any failure here MUST NOT block or alter the MCP response.
    """
    try:
        shadow_store.increment("orders_processed")
        
        # 1. Generate Order
        order_id = f"ord_shadow_{uuid.uuid4().hex[:8]}"
        order = OperationalOrder(
            order_id=order_id,
            consumer="mcp_shadow_pipeline",
            issued_at=datetime.now(timezone.utc).isoformat(),
            objective=objective or "unknown",
            parameters={"port_id": port_id}
        )
        
        # 2. Extract Evidence
        evidences = OrderExtractor.extract_from_assess_logistics(order, mcp_result)
        
        for ev in evidences:
            if ev.logical_id in shadow_store.evidences:
                shadow_store.increment("deduplicated_evidence")
            else:
                shadow_store.evidences[ev.logical_id] = ev
                shadow_store.increment("new_evidence")
                
        # 3. Resolve Entities
        vessel = None
        for ev in evidences:
            if ev.entity.type == "vessel":
                from src.reconstruction.models import VesselEntity, IdentityState
                import hashlib
                name_hash = hashlib.md5(ev.entity.raw_name.encode('utf-8')).hexdigest()[:8]
                v_stable_id = f"urn:vessel:name:{name_hash}"
                if v_stable_id in shadow_store.vessels:
                    shadow_store.increment("updated_entities")
                    vessel = shadow_store.vessels[v_stable_id]
                else:
                    vessel = VesselEntity(identity_state=IdentityState.CANDIDATE, name=ev.entity.raw_name)
                    shadow_store.vessels[v_stable_id] = vessel
                    shadow_store.increment("new_entities")
            elif ev.entity.type == "port":
                p_stable_id = f"urn:port:{ev.entity.id}"
                if p_stable_id not in shadow_store.vessels:
                    shadow_store.vessels[p_stable_id] = ev.entity
                    shadow_store.increment("new_entities")

        # 4. PortCall
        from src.reconstruction.models import PortCall
        pc = PortCall(port=port_id, vessel_id=vessel.stable_id if vessel else None)
        if pc.stable_id in shadow_store.portcalls:
            shadow_store.increment("updated_portcalls")
        else:
            shadow_store.portcalls[pc.stable_id] = pc
            shadow_store.increment("new_portcalls")

        # 5. ShipmentReconstruction
        # A shipment is tied to the portcall in this simplified scope
        shipment_key = f"shp_{pc.stable_id}"
        is_new_shipment = False
        if shipment_key not in shadow_store.shipments:
            shadow_store.shipments[shipment_key] = ShipmentReconstruction(shipment_id=shipment_key)
            shadow_store.increment("new_shipments")
            is_new_shipment = True
        else:
            shadow_store.increment("updated_shipments")
            
        shipment = shadow_store.shipments[shipment_key]
        
        engine = ReconstructionEngine()
        for ev in evidences:
            engine.apply_evidence(shipment, ev)
            
        # 6. Apply Hypothesis Engine
        h_engine = HypothesisEngine()
        hyp = h_engine.evaluate_cargo(shipment)
        if hyp:
            if hyp.epistemic_state == EpistemicState.CONTRADICTION:
                shadow_store.increment("contradictions")
            
            if hyp.stable_id not in shipment.hypotheses:
                h_engine.apply_hypothesis(shipment, hyp)
                shadow_store.increment("new_hypotheses")
            
    except Exception as e:
        logger.error(f"Shadow pipeline failed: {e}")
        shadow_store.increment("pipeline_failures")
