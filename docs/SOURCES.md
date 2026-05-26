# Sources — Real-World Format Research

---

## 1. SAP Fuel & Procurement

### What I researched
SAP's transaction MB51 (Material Document List) and ME2M (Purchase Orders by Material). Both produce flat-file exports via SAP GUI's "Export to Local File" function. I also reviewed the SAP IDoc documentation (WE02/WE05), OData services for MM module in S/4HANA (`/sap/opu/odata/SAP/MM_PUR_PO_MARA_SRV/`), and BAPI_GOODSMVT_GETLIST for programmatic goods movement retrieval.

### What I learned
- SAP GUI exports to CSV with German column headers by default in DE/AT/CH system locales. `Buchungsdatum` = posting date, `Menge` = quantity, `Einheit` = unit of measure, `Werk` = plant, `Kostenstelle` = cost centre.
- Dates are always DD.MM.YYYY in German locales, YYYY-MM-DD in some English locales — you must handle both.
- Quantities use comma as decimal separator in DE locale (`1.234,56` = 1234.56). My parser does `.replace(',', '.')` after stripping thousands separators.
- Unit codes are SAP-internal: L = litres, KG = kilograms, M3 = cubic metres, KWH = kilowatt-hours, TON = metric tonne. NOT SI: `G` = gram, `T` = tonne (same as TON in SAP but coded differently).
- Movement type 261 = goods issue to production/consumption. 101 = goods receipt into stock (NOT consumption — must filter out). A real export includes both; naively summing all rows double-counts fuel.
- Material numbers are 18-character zero-padded strings. The left-padded zeros are usually stripped in reporting.

### What my sample data looks like and why
`sample_sap.csv` contains: 9 fuel consumption rows (movement type 261), 1 goods receipt (101, should be skipped), 1 non-fuel procurement row (office supplies). The fuel rows cover diesel, petrol, LPG, and natural gas across 3 plant codes and 3 months. One row has an implausibly large quantity (42,000 KG diesel) to trigger anomaly detection. Headers are German to test the translation layer.

### What would break in a real deployment
- **Encoding**: SAP can export in UTF-8 or ISO-8859-1 (Latin-1). German umlauts in material descriptions (e.g. "Heizöl") break on UTF-8 decode. Need encoding detection (chardet).
- **Custom movement types**: Many SAP clients configure custom movement types (Z-prefix, e.g. Z61). Our hardcoded filter list misses these — need a per-client config table.
- **Plant code lookup**: Plant codes like "1000" are meaningless without a `T001W` plant master table. Joining scope decisions to specific plants (e.g. leased vs owned) requires that lookup. We store the code but can't resolve ownership without it.
- **Currency/value data**: We capture amount but don't use it. Spend-based Scope 3 would need this, along with FX conversion for multi-currency clients.
- **IDoc or OData at scale**: At >100k rows/month, file upload becomes operationally burdensome. Would need the scheduled OData pull.

---

## 2. Utility / Electricity

### What I researched
UK utility portal exports from: EDF Business, Octopus Energy for Business, ScottishPower Business, British Gas Business. Also reviewed: Green Button (ESPI) standard documentation (used by US utilities), half-hourly (HH) metering data format (14 Settlement Periods × 48 per day), and MPAN structure (Meter Point Administration Number, 21-digit UK identifier).

### What I learned
- Portal CSV exports are the de-facto standard. Every major UK business utility has a "Download usage data" function that produces CSV.
- **Billing periods don't align to calendar months.** A meter read might be taken on the 17th of each month, producing billing periods like 17 Jan – 16 Feb. Reports aggregating by calendar month must handle this.
- **Meter IDs**: UK electricity meters are identified by MPAN (21-digit). Exports may include the full MPAN, a shortened form, or a site reference. Multiple MPANs per site are common (different circuits, different buildings).
- **Units**: kWh is standard for monthly bills. HH data exports are in kWh per half-hour. MWh appears in some large industrial exports. GJ is rare but appears in combined energy reports.
- **Grid emission factor**: DEFRA publishes a UK grid average annually (2023: 0.21233 kgCO2e/kWh). For market-based accounting, clients with renewable energy contracts can use their supplier's factor, which may be near-zero. Our prototype uses location-based only.

### What my sample data looks like and why
`sample_utility.csv` has 3 meters across 3 sites: a factory (high consumption ~48-52 MWh/month), an office (12-13 MWh), and a warehouse (8-9 MWh). Billing periods deliberately don't align to calendar months for MTR-002 (starts 17th) and MTR-003 (starts 5th) to exercise the billing period logic. 9 rows covering Q1 2024.

### What would break in a real deployment
- **HH data volume**: A large factory on HH metering produces 17,520 rows/year. We'd need a pre-aggregation step (daily or monthly totals before storing as EmissionRecords).
- **PDF bills**: ~30% of SME sites still receive paper/PDF bills with no portal export. Would need per-utility PDF templates or an OCR pipeline.
- **Gas meters**: Natural gas meters appear in the same portal export alongside electricity. Gas requires a different emission factor (combustion, not grid). Our parser ignores non-electricity rows — a real system needs to handle gas as Scope 1.
- **Negative consumption**: Some exports include credit notes (negative rows). Our anomaly detector flags these but doesn't reverse them — a real system needs to match credits to original consumption rows.
- **Renewable certificates**: REGOs (Renewable Energy Guarantees of Origin) affect market-based Scope 2. Not modelled.

---

## 3. Corporate Travel

### What I researched
Concur Travel & Expense REST API (SAP Concur Developer Center), Navan (formerly TripActions) API documentation and webhook schemas, DEFRA 2023 business travel emission factors (Table 14: Business travel — air, Table 15: Business travel — land), ICAO Carbon Emissions Calculator methodology, and GHG Protocol Scope 3 Category 6 guidance.

### What I learned
- **Concur**: Exposes `/api/v3.0/expense/reports` (expense reports) and `/travel/v3/trips` (trip records). Trip records contain segments with type (air/hotel/car/rail). Requires OAuth 2.0 company-level token. JSON responses.
- **Navan**: REST API + webhooks. Trip objects contain an array of "travel items" with type, origin, destination, dates, and optionally `carbon_kg` (Navan computes its own estimate). We use our own calculation for consistency.
- **Distance data**: Concur trip records sometimes include `distance_km`; often they don't — you only get IATA codes. Navan more consistently provides distance. We fall back to haversine great-circle calculation.
- **Cabin class multiplier**: DEFRA 2023 factors are class-specific. Economy = 0.1553 kgCO2e/km, Business = 0.4290 kgCO2e/km (2.76× economy), First = 0.5765 kgCO2e/km. This matters significantly for a company with executive travel.
- **Hotels**: DEFRA provides per-room-night factors by country. UK = 20.8 kgCO2e, US = 31.2 kgCO2e, FR = 15.7 kgCO2e. These are average-across-hotel-categories — star rating factors exist but aren't widely used yet.
- **Ground transport**: Taxi/rideshare ≈ 0.1489 kgCO2e/km (average UK car), Rail ≈ 0.0035 kgCO2e/km (UK national rail), Bus ≈ 0.0273 kgCO2e/km.

### What my sample data looks like and why
`sample_travel.json` follows Navan's trip structure with a `trips` array, each containing a `segments` array. 5 trips covering: a return LHR-JFK in economy (Alice) and business (Bob, higher footprint to test anomaly flagging), a short-haul LHR-CDG trip, a LHR-DXB trip, and a domestic UK rail trip (no flights). Mix of flight + hotel + ground segments. Hotel countries cover US, FR, AE (Dubai), UK to exercise country-specific hotel factors.

### What would break in a real deployment
- **Airport lookup gaps**: Our IATA coordinate table has ~25 airports. A route like MAN-ATH (Manchester to Athens) would fail distance lookup and produce a parse error. Production needs a full IATA database (7,000+ airports) or integration with a distance API (Great Circle Mapper, OurAirports).
- **Booking class vs cabin class**: Booking classes (Y, J, C, F...) in Concur records map to cabin class but the mapping varies by airline. Our parser accepts a `cabin_class` string directly — in production you'd need a booking-class → cabin-class lookup per airline.
- **Group bookings**: If a company books 50 seats on one flight, the Concur record may appear as one row with quantity=50. Our parser treats each segment as one passenger. Need to check the `quantity` or `travelers_count` field.
- **Expense-only records**: Some employees book travel outside the corporate tool and submit expense claims. These arrive as `expense_type = 'airline'` in Concur expense reports with a `£ amount` but no segment data. Spend-based emission factors would be needed as a fallback.
- **Rail without distance**: UK domestic rail in Concur often just says "Rail" with a cost but no origin/destination. Without station codes, we can't compute distance. A mapping of route description → distance would be needed.
