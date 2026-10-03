# AETHER-X Persistence Roadmap: Phase 4B Decision Record

## 1. Context

The Shadow Pipeline has successfully established identity resolution, semantic accumulation, and epistemic safeguarding. Before replacing the Shadow Store with a permanent storage backend in `oracle.duckdb`, the ideal persistence paradigm must be decided.

## 2. Conceptual Persistence Options

### Option A: Pure Relational Tables
- **Concept:** Highly normalized schema. Tables for `vessels`, `port_calls`, `shipments`, `evidence`, `shipment_evidence_links`.
- **Pros:** Perfect for DuckDB analytical queries. Easy to enforce foreign keys.
- **Cons:** Rigid. Handling varying epistemic states and arrays of `supporting_evidence_ids` for *each field* (cargo, destination, etc.) requires massive sparse tables or anti-patterns like vertical EAV (Entity-Attribute-Value).

### Option B: Pure Graph Representation
- **Concept:** Nodes (Vessels, Ports, Shipments, Evidence, Sources) and Edges (SUPPORTS, CONTRADICTS, AT_LOCATION).
- **Pros:** Native representation of the Evidence Graph. Easy to traverse lineage.
- **Cons:** DuckDB is relational. Forcing a graph database requires introducing Neo4j/Gremlin, violating the single-binary deployment constraint of AETHER-X.

### Option C: Hybrid Relational + Evidence Graph (Recommended)
- **Concept:** 
  - **Relational Backbone:** Core entities with stable URNs (`vessels`, `port_calls`, `voyages`) are standard relational tables.
  - **JSON Document Extension:** The `ShipmentReconstruction` object is stored as a structured JSON blob in a DuckDB JSON column, embedding the `ShipmentField` complex arrays.
  - **Evidence Ledger:** A dedicated `evidence_ledger` table stores all immutable `RichEvidence` rows.
- **Pros:** 
  - Aligns with DuckDB's excellent native JSON support.
  - Keeps operational simplicity (one database).
  - Fast analytical queries on relational backbones.
  - Total flexibility for the complex epistemic fields inside the shipment document.

## 3. Evaluation Matrix

| Metric | Relational | Graph | Hybrid (JSON+Relational) |
| :--- | :--- | :--- | :--- |
| **Provenance tracking** | Difficult | Native | Excellent (via Ledger + Arrays) |
| **Temporal queries** | Excellent | Good | Excellent |
| **Entity Resolution updates** | Good | Excellent | Good |
| **M2M Queries / Speed** | Fast | Medium | Fast |
| **Operational Simplicity** | Native | Requires new DB | Native (DuckDB) |

## 4. Implementation Constraints (Phase 4B)

The transition to permanent persistence will enforce the Hybrid Model.
- **No deletions.** The `evidence_ledger` is append-only.
- Shipments will be serialized/deserialized to Pydantic models from JSON.
- `shadow_store.py` will serve as the transition blueprint but its in-memory dictionaries will be replaced by DuckDB statements reading/writing from/to the `oracle.duckdb` connection.

*Current Status: Awaiting authorization to begin Phase 4B migrations.*
