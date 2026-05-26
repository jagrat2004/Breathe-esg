# Tradeoffs — Three Things Deliberately Not Built

---

## 1. No Versioned Emission Factor Table

**What I did instead:** Emission factors are hardcoded in each parser and stored denormalised on every `EmissionRecord` (fields: `emission_factor`, `emission_factor_source`, `emission_factor_unit`).

**Why I didn't build it:** A proper versioned `EmissionFactor` table would look like:
```
EmissionFactor(id, category, fuel_type, unit, value, source, valid_from, valid_to)
```
With a FK from `EmissionRecord.emission_factor_version`. This enables: annual factor updates (DEFRA publishes new factors every June), bulk recalculation of historical records, and a UI to show "this record used DEFRA 2022 — DEFRA 2023 would change it by +2.3%".

**The tradeoff:** Without this, updating emission factors requires re-ingesting data. For a real client preparing an annual GHG inventory, this would be painful — factors change year to year and you want one button to recalculate. I chose not to build it because the 4-day constraint meant the data model and parsing quality were higher leverage, and the denormalised approach still satisfies the audit requirement (auditors can see exactly what factor was applied).

---

## 2. No Real-Time API Pull (Scheduled Ingestion Jobs)

**What I did instead:** File upload only. The analyst manually downloads a CSV or JSON from the source system and uploads it.

**Why I didn't build it:** A production ingestion system would have scheduled pull jobs:
- SAP: Celery/cron task calling an OData endpoint or SFTP pickup
- Utility: OAuth2 token refresh + Green Button API polling
- Travel: Concur/Navan webhook receiver or scheduled API pull

This requires: a task queue (Celery + Redis), credential storage (encrypted with KMS), retry logic, idempotency keys (don't double-import the same data), and per-client connection configs.

**The tradeoff:** The upload model is actually fine for the analyst review use case — it puts a human in the loop before data reaches the system, which some clients prefer. The review dashboard is the high-value part; automated pull is an operational improvement that would come after the data model is validated.

---

## 3. No Scope 3 Category 1 (Purchased Goods & Services)

**What I did instead:** SAP procurement rows (non-fuel materials) are parsed but silently skipped when the material description doesn't indicate a fuel type.

**Why I didn't build it:** Scope 3 Category 1 (upstream emissions from purchased goods and services) is the hardest category in ESG accounting. It requires:
- Spend-based emission factors ($/£ spent × kgCO2e per £ of spend by category)
- Or activity-based factors (kg of steel × kgCO2e/kg of steel)
- A mapping from SAP material numbers / commodity codes to emission factor categories
- An entirely separate material taxonomy lookup table

The DEFRA spend-based factors vary by 50–100× across commodity categories. Without the taxonomy mapping (which is client-specific), any number we produce would be unreliable. Including unreliable Scope 3 Category 1 data in an auditor-facing system would be worse than omitting it.

**What I'd need to build it properly:** A `CommodityMapping` table per tenant, a UI for the sustainability team to map their SAP material groups to DEFRA commodity categories, and a quality flag distinguishing spend-based estimates from activity-based measurements. That's a 2-week feature, not a 4-day prototype add-on.
