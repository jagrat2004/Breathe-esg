# Decisions — Breathe ESG Prototype

Every ambiguity resolved, what I chose, why, and what I'd ask the PM.

---

## SAP: Format Choice — Flat-File CSV (MB51/ME2M export)

**Chosen:** SAP flat-file CSV export, transaction MB51 (material document list) or ME2M (purchase orders).

**Why not IDoc:** IDoc is the native SAP EDI format (XML-structured), but it requires EDI middleware (SAP XI/PI/PO or an EDI gateway) that is never exposed to third parties. In 10 years of enterprise integrations, no sustainability team emails you an IDoc.

**Why not OData (S/4HANA):** OData via `/sap/opu/odata/` requires live OAuth2 connectivity to the client's SAP tenant, firewall rules, and scope permissions that take weeks of IT approval. We can't build around that for an onboarding prototype.

**Why flat-file CSV:** This is the actual artifact sustainability leads send. A finance user runs MB51 in SAP GUI, exports to Excel/CSV, and emails or shares it. It's messy (German headers, DD.MM.YYYY dates, comma-as-decimal in some locales) but parseable. We handle the real-world messiness.

**What I'd ask the PM:** Is this client on ECC or S/4HANA? If S/4HANA and IT can provide a service account, we could schedule an OData pull directly — which removes the human-in-the-loop upload step. What's the data freshness requirement?

---

## SAP: Movement Type Filtering

**Chosen:** Only process movement types 261, 201, 551, 601, 641 (consumption events). Skip 101 (goods receipt into stock).

**Why:** A goods receipt (101) is stock arriving in the warehouse — it's not combustion. Including it would double-count: you'd get the receipt AND the eventual consumption (261) of the same fuel. Real MB51 exports include all movement types by default.

**What I'd ask:** Does this client track fuel via direct consumption postings (261) or via stock management? If they use a fuel tank as a stock location, we need goods issues (201/261), not receipts.

---

## Utility: Format Choice — Portal CSV Export

**Chosen:** Portal CSV (EDF, Octopus Business, ScottishPower, etc.)

**Why not PDF:** PDF bills are the most common format for small sites, but: (a) every utility has a different layout, (b) scanned PDFs fail entirely, (c) even pdfplumber fails on multi-column tariff tables. Reliable PDF parsing requires a per-utility template library — out of scope for a 4-day prototype.

**Why not Green Button / ESPI API:** The ESPI standard (XML-based) is widely adopted by US utilities but barely exists in UK/EU. UK enterprise utilities offer proprietary APIs with separate onboarding. Portal CSV is the universal fallback that facilities teams actually use today.

**What I'd ask:** Does this client have more than 10 meters? If yes, the half-hourly (HH) metering data export format differs from monthly billing data — it produces 17,520 rows/year/meter. We'd want to aggregate to daily before storing.

---

## Utility: Billing Period vs Calendar Month

**Chosen:** Store `period_start` / `period_end` verbatim; use midpoint as `activity_date` for aggregation.

**Why:** Billing periods like 17 Jan – 14 Feb don't fit neatly into monthly reports. Splitting proportionally (13/28 days to Jan, 15/28 to Feb) is more accurate but adds complexity and makes the origin of each record less obvious. Midpoint is a reasonable approximation that keeps one row = one bill.

---

## Travel: Format Choice — JSON (Concur/Navan API style)

**Chosen:** JSON file upload simulating a Concur or Navan REST API export.

**Why JSON not CSV:** A single trip has multiple segments (flight + hotel + ground transport). CSV flattens this — either one row per trip (losing segment detail) or one row per segment (losing trip context). JSON's nested structure maps naturally to the data.

**Why Concur/Navan:** These two platforms cover ~60–65% of Fortune 500 corporate travel spend. Both expose REST JSON APIs. Our JSON schema matches what Concur's `/expense/reports` and Navan's trip webhook return with minor normalization.

**What I'd ask:** Is the client's travel platform Concur, Navan, or something else? Does their platform output include `distance_km` or only airport codes? (Our parser handles both via haversine fallback, but it's good to know.)

---

## Flight Distance Calculation

**Chosen:** Haversine great-circle distance when `distance_km` is not provided by the platform.

**Why not actual flight path:** Real flight paths are longer than great-circle (typically +10-15% for routing, holding patterns). DEFRA and ICAO both acknowledge this; some factor sets include a detour factor. We apply haversine and note the assumption in metadata.

**What I'd ask:** Does the client want us to apply a routing uplift factor? DEFRA 2023 technical guidance suggests using a standard uplift of ~8% for economy and more for long-haul. Currently not applied.

---

## Emission Factors

**Chosen:** DEFRA 2023 Greenhouse Gas Conversion Factors for Company Reporting.

**Why DEFRA:** This is the UK government standard, freely available, annually updated, and what most UK enterprise sustainability reports cite. For a UK-headquartered client it's the natural default.

**Limitations:** The client operates internationally (plants in multiple countries). For Scope 2 electricity, grid factors are country-specific — our utility parser accepts a `country` parameter for this. For Scope 3 travel, DEFRA provides global flight factors so no country correction is needed.

**What I'd ask:** Does the client want market-based or location-based Scope 2 accounting? Market-based uses their specific energy supplier's factor (possibly a green tariff). Location-based (what we implement) uses the national grid average. Many clients do both for disclosure purposes.

---

## What Subset of Each Source We Handle

**SAP:** Fuel combustion (261/201 goods issue of fuel materials). We skip: procurement of non-fuel goods (Scope 3 Category 1), plant-to-plant transfers, returns, and reversals. We recognise diesel, petrol, LPG, natural gas, heavy fuel oil. We skip: refrigerants, process chemicals, purchased heat.

**Utility:** Single electricity meter type, monthly or billing-period granularity. We skip: gas meters (overlap with SAP natural gas), water, district heating, half-hourly HH data (different format), demand response credits.

**Travel:** Flights, hotels, ground transport (taxi/rail/bus/rideshare). We skip: per-diem expenses, meals, car ownership emissions (Scope 1), rental car distance not provided, international rail between non-UK airports not in our lookup table.
