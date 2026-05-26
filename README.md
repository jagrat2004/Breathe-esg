# Breathe ESG — Emissions Ingestion & Review Platform

A Django REST + React prototype for ingesting, normalising, and reviewing emissions data from three enterprise sources: SAP fuel/procurement, utility electricity portal exports, and corporate travel (Concur/Navan).

## Live Demo

> Deploy via `render.yaml` — see Deployment section below.

**Demo credentials:**
- `analyst / demo1234` — analyst role (review, approve, reject)
- `admin / admin1234` — admin role + Django admin at `/admin`

---

## Architecture

```
frontend/          React + Recharts dashboard
backend/
  config/          Django settings, URLs, WSGI
  tenants/         Multi-tenant isolation (Tenant, TenantUser)
  ingestion/       DataSource, IngestionBatch, RawRow models + parsers
    parsers/
      sap_parser.py      SAP flat-file CSV (MB51/ME2M)
      utility_parser.py  Utility portal CSV
      travel_parser.py   Concur/Navan JSON trips
  emissions/       EmissionRecord model, views, dashboard API
docs/
  MODEL.md         Data model rationale
  DECISIONS.md     Every ambiguity resolved
  TRADEOFFS.md     Three deliberate omissions
  SOURCES.md       Real-world format research
sample_data/
  sample_sap.csv
  sample_utility.csv
  sample_travel.json
```

---

## Local Setup

```bash
# Backend
cd backend
pip install -r requirements.txt
python manage.py migrate
python seed_data.py       # creates demo users + sample records
python manage.py runserver

# Frontend (separate terminal)
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/auth/token/` | Get auth token |
| GET | `/api/dashboard/` | KPIs + charts data |
| GET | `/api/records/` | List records (filterable) |
| POST | `/api/records/{id}/approve/` | Approve a record |
| POST | `/api/records/{id}/reject/` | Reject a record |
| POST | `/api/records/bulk_approve/` | Bulk approve by IDs |
| POST | `/api/records/lock_approved/` | Lock all approved → audit |
| POST | `/api/ingest/` | Upload + parse a file |
| GET | `/api/batches/` | Ingestion history |

**Filter params on `/api/records/`:** `scope`, `status`, `source_type`, `category`, `anomaly=true`

---

## Deployment (Render)

1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect your repo — Render reads `render.yaml` automatically
4. It will create: PostgreSQL DB, Django backend web service, React static site
5. Set `REACT_APP_API_URL` in frontend env to the backend's `.onrender.com` URL

---

## Sample Data

Upload files from `sample_data/` via the Ingest page to test parsing:

- **`sample_sap.csv`** — German-header SAP export with fuel consumption rows, one goods receipt (auto-skipped), one non-fuel row, one anomaly (42,000 kg diesel)
- **`sample_utility.csv`** — 3 meters, billing periods misaligned to calendar months
- **`sample_travel.json`** — 5 trips, flights (economy + business class), hotels (UK/US/FR/AE), rail and taxi ground transport
