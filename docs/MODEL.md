# Data Model — Breathe ESG Ingestion Platform

## Overview

Four layers: **Tenant** (isolation root) → **DataSource / IngestionBatch / RawRow** (provenance) → **EmissionRecord** (canonical normalised event) → **review state** (analyst workflow).

---

## Multi-Tenancy

Every data-bearing table has a hard `tenant` FK. All querysets are filtered at the view layer via `get_tenant(request)` — a user can only see records belonging to their tenant.

`TenantUser` links `auth.User` to a `Tenant` with role (`analyst`, `admin`, `auditor`). Role stored for future RBAC enforcement.

---

## Scope Classification

| Source | Category | Scope | Rationale |
|--------|----------|-------|-----------|
| SAP | `fuel_combustion` | 1 | Direct combustion at owned facilities |
| Utility | `electricity` | 2 | Purchased electricity, location-based method |
| Travel | `flight` | 3 | Category 6: Business travel |
| Travel | `hotel` | 3 | Category 6: Business travel |
| Travel | `ground_transport` | 3 | Category 6: Business travel |

Scope is an integer (1/2/3) — not a string — so `GROUP BY scope` queries work cleanly.

---

## Source-of-Truth Tracking

**`RawRow`** — immutable. Every row written verbatim to `raw_data` (JSONField) before parsing. Never mutated. `parse_error` records row-level failures. Re-parsing is always possible.

**`IngestionBatch`** — file-level provenance. Who uploaded, when, filename, row counts, error counts. Links `EmissionRecord → IngestionBatch → DataSource → Tenant`.

**`EmissionRecord.edit_history`** — post-ingestion corrections. `record_edit()` appends `{field, old_value, new_value, edited_by, edited_at}` to a JSONField list. `is_edited = True` is set. Original `RawRow` unchanged.

---

## Unit Normalisation

All incoming quantities converted to canonical units before storage:

| Field | Unit | Covers |
|-------|------|--------|
| `quantity_kwh` | kWh | Electricity, gas via calorific value |
| `quantity_kg` | kg | Fuel mass |
| `quantity_km` | km | Flight and ground distances |
| `quantity_nights` | int | Hotel stays |

Original preserved in `original_quantity` + `original_unit`. Conversion logic lives in parsers, not the model — auditable and independently testable.

Output is always `co2e_kg`. Tonnes computed at query time (`co2e_kg / 1000`) to avoid double-conversion drift.

---

## Emission Factors

Stored denormalised on each record: `emission_factor`, `emission_factor_source` (e.g. "DEFRA 2023"), `emission_factor_unit` (e.g. "kgCO2e/kWh"). Records are self-describing for auditors. Historical records retain the factor applied at ingestion — correct for GHG inventory.

---

## Audit Trail

`status = 'locked'` after analyst approval + auditor lock. Locked records cannot be edited — one-way ratchet matching real GHG inventory practice.

`reviewed_by + reviewed_at + review_note` set on approval/rejection. Complete chain: original file → RawRow → parse result → corrections (edit_history) → analyst sign-off → lock.

---

## Anomaly Detection (auto-flagging at ingest)

- `co2e_kg > 100,000` — almost certainly a data error
- `co2e_kg < 0` — negative without reversal movement type
- Utility `consumption_kwh > 500,000` in one billing period
- Flight `co2e_kg > 5,000` per segment (flags premium cabin long-haul)

Flagged records land in `status = 'flagged'`, highlighted in UI, excluded from bulk-approve.

---

## Design Choices

**JSONField for metadata**: Each source has different contextual fields. Avoids nullable column explosion. Queryable via Postgres GIN index in production.

**No separate EmissionFactor table**: Factors baked into parsers and stored denormalised. Production would have versioned `EmissionFactor(factor, unit, source, valid_from, valid_to)` for annual DEFRA updates.

**Billing period midpoint as activity_date**: Utility periods span 28–31 days, don't align to months. Store full `period_start`/`period_end`, compute midpoint for `activity_date`. Monthly aggregations stay sensible without losing original data.
