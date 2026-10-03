# AETHER-X Persistence Contract: Reconstruction Layer

This document defines the formal persistence and lifecycle contracts for the Shipment Reconstruction Layer before transitioning to physical table structures in Oracle.

## 1. Persistent Entities & Boundaries

| Entity | Type | Lifecycle / Immutability | Identity |
| :--- | :--- | :--- | :--- |
| **Evidence** | Transversal | **IMMUTABLE**. Never altered once extracted. | `logical_id` (SHA256 of Source+Claim+Time+Entity). Operational. |
| **OperationalOrder** | Trigger | **IMMUTABLE**. Short-lived event. | `order_id` (UUID). Operational. |
| **Vessel** | Entity | Accumulative (Mergeable). | `stable_id` (`urn:vessel:imo:{imo}` or hash). Stable. |
| **Voyage** | Event/Entity | Accumulative. | `stable_id` (`urn:voyage:{vessel}_{year}_{cycle}`). Stable. |
| **PortCall** | Event | Accumulative. | `stable_id` (`urn:portcall:{port}_{vessel}`). Stable. |
| **Location** | Entity | Static Reference. | Natural (e.g. UN/LOCODE `BRSSZ`). |
| **Party** | Entity | Accumulative. | Natural (Tax ID / Name hash). |
| **Route** | Entity/Path | Accumulative. | Operational hash of ordered nodes. |
| **Cargo** | Object | Accumulative. | Operational candidate hash. |
| **ShipmentReconstruction** | Accumulator | **MUTABLE**. Evolves with new evidence. | **PROVISIONAL OPERATIONAL AGGREGATOR** (`urn:shipment:{portcall_id}`). |
| **Hypothesis** | Inference | Mutable state, Immutable rationale. | Hash of claim + supporting evidence IDs. |

## 2. Identity Classifications

1. **Natural Identifier:** Found in physical reality (e.g., IMO number, UN/LOCODE). Used for definitive entity resolution.
2. **Operational Identifier:** Transitory ID generated for tracking processing runs (e.g., UUID for `OperationalOrder`). NEVER used to deduplicate domain entities.
3. **Stable Identifier:** A URN-based identifier deterministic by design (e.g., `urn:portcall:BRSSZ:1234567`). Safe for graph correlation and foreign keys.
4. **Source Identifier:** The primary key used by the third-party provider. Useful only within the scope of that provider's data silo.

**Shipment Identity Protocol:**
`urn:shipment:{portcall_id}` is formally defined as a **PROVISIONAL OPERATIONAL AGGREGATOR**. It is used while the extraction pipeline lacks enough high-level cargo/shipper identifiers to split a `PortCall` into multiple distinct `Shipments`. Once semantic identifiers (e.g., Consignee Tax ID + Cargo Type) are captured, the system transitions the aggregator into one or more `IDENTIFIED` or `CANDIDATE` shipments.

## 3. Relationships & Cardinality

- **Vessel 1 → N Voyage**: A vessel conducts many voyages over time.
- **Voyage 1 → N PortCall**: A voyage is a continuous path linking multiple port events.
- **PortCall 1 → N ShipmentReconstruction**: A single port call can serve dozens of unique commercial shipments.
- **ShipmentReconstruction → N Evidence**: A shipment is supported by transversal evidence arrays across its fields.
- **ShipmentReconstruction → N Hypothesis**: A shipment can have multiple competing hypotheses.

## 4. Temporal Model

Time in the domain is not artificial. If we do not know when something occurred, it remains `NULL`.

- `source_observed_at`: The exact physical moment the fact was captured by the sensor (e.g., AIS ping time). Can be NULL.
- `retrieved_at`: The system time the M2M query fetched the data. Always present.
- `effective_at`: The timestamp at which a legal or commercial status becomes active.
- `valid_from` / `valid_to`: Bitemporal markers for entity state snapshots.
- `created_at` / `updated_at`: Database system ingestion markers.

## 5. Delete & Reversibility Contract

**No silent physical deletions.**

- **Source disappears:** If a source retroactive invalidates an observation, a new `OperationalOrder` emits an inverted `Evidence` (tombstone).
- **Evidence invalidation:** Removing evidence from an entity recalculates the entity's epistemic state (reversibility). If `vessel.current_value` loses its only `OBSERVED` evidence, it downgrades.
- **Hypothesis loses support:** If underlying evidence is invalidated, the hypothesis state shifts to `UNKNOWN` or `CONTRADICTION`, but the hypothesis record is preserved for audit.
