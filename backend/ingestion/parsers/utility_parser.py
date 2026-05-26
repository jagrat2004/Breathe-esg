"""
Utility / Electricity Parser

Format chosen: Portal CSV export.
Justification: 
  - PDF bills are the most common format but extremely hard to parse reliably 
    (inconsistent layouts per utility, pdfplumber fails on scanned bills).
  - Utility APIs exist (Green Button, ESPI) but adoption is patchy — mainly US 
    residential, not UK/EU enterprise.
  - Portal CSV exports (e.g. from EDF, Octopus, ScottishPower business portals)
    are what facilities teams actually download and send. They're structured enough
    to parse reliably and cover 80%+ of real enterprise clients.

Key considerations:
  - Billing periods don't align with calendar months (e.g. 17 Jan–14 Feb)
  - Multiple meters per site (half-hourly HH data vs monthly)
  - Units: kWh is standard but some exports give MWh or GJ
  - We normalise to kWh and apply a location-specific grid emission factor
"""

import csv
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

# Grid emission factors kgCO2e/kWh (DEFRA 2023, location-based)
GRID_FACTORS = {
    'UK':    0.2128,
    'DE':    0.4140,
    'FR':    0.0561,
    'US':    0.3860,
    'IN':    0.7080,
    'DEFAULT': 0.2128,  # UK as conservative default
}

UNIT_CONVERSIONS = {
    'KWH':  1.0,
    'MWH':  1000.0,
    'GWH':  1_000_000.0,
    'GJ':   277.778,
    'MJ':   0.27778,
}

HEADER_ALIASES = {
    # Octopus-style
    'consumption (kwh)': 'consumption_kwh',
    'start':             'period_start',
    'end':               'period_end',
    'meter serial':      'meter_id',
    'mpan':              'meter_id',
    'site':              'site_name',
    # Generic
    'consumption':       'consumption_raw',
    'units':             'unit',
    'period start':      'period_start',
    'period end':        'period_end',
    'billing period start': 'period_start',
    'billing period end':   'period_end',
    'meter id':          'meter_id',
    'meter number':      'meter_id',
    'site name':         'site_name',
    'location':          'site_name',
    'kwh':               'consumption_kwh',
    'usage kwh':         'consumption_kwh',
    'tariff':            'tariff',
    'rate':              'tariff',
    'amount':            'amount_gbp',
    'cost':              'amount_gbp',
    'country':           'country',
}


def normalise_header(h: str) -> str:
    return HEADER_ALIASES.get(h.strip().lower(), h.strip().lower().replace(' ', '_'))


def parse_utility_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d',
                '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_utility_csv(file_content: bytes, country: str = 'UK') -> list[dict]:
    """
    Parse utility portal CSV. Returns list of row result dicts.
    """
    results = []
    try:
        text = file_content.decode('utf-8', errors='replace')
    except Exception as e:
        return [{'ok': False, 'row': 0, 'data': {}, 'errors': [f'Decode error: {e}']}]

    reader = csv.DictReader(io.StringIO(text))
    raw_headers = reader.fieldnames or []
    header_map = {h: normalise_header(h) for h in raw_headers}

    ef = GRID_FACTORS.get(country.upper(), GRID_FACTORS['DEFAULT'])
    ef_source = f'DEFRA 2023 grid ({country})'

    for row_num, row in enumerate(reader, start=1):
        norm = {header_map.get(k, k): (v.strip() if v else '') for k, v in row.items()}
        errors = []

        # --- Consumption ---
        kwh_val = None
        if 'consumption_kwh' in norm and norm['consumption_kwh']:
            try:
                kwh_val = Decimal(norm['consumption_kwh'].replace(',', ''))
            except InvalidOperation:
                errors.append(f"Cannot parse consumption_kwh: '{norm['consumption_kwh']}'")
        elif 'consumption_raw' in norm and norm['consumption_raw']:
            # raw consumption with separate unit column
            try:
                raw_qty = Decimal(norm['consumption_raw'].replace(',', ''))
                unit = norm.get('unit', 'KWH').upper().strip()
                conv = UNIT_CONVERSIONS.get(unit)
                if conv:
                    kwh_val = raw_qty * Decimal(str(conv))
                else:
                    errors.append(f"Unknown unit: '{unit}'")
            except InvalidOperation:
                errors.append(f"Cannot parse consumption: '{norm.get('consumption_raw')}'")
        else:
            errors.append('No consumption column found')

        # --- Dates ---
        start_raw = norm.get('period_start', '')
        end_raw = norm.get('period_end', '')
        period_start = parse_utility_date(start_raw)
        period_end = parse_utility_date(end_raw)
        if not period_start:
            errors.append(f"Cannot parse period_start: '{start_raw}'")
        if not period_end:
            errors.append(f"Cannot parse period_end: '{end_raw}'")

        # Use midpoint of billing period as activity_date
        activity_date = None
        if period_start and period_end:
            mid = period_start + (period_end - period_start) / 2
            activity_date = mid.date()
        elif period_start:
            activity_date = period_start.date()

        # --- CO2e ---
        co2e_kg = None
        if kwh_val:
            co2e_kg = round(float(kwh_val) * ef, 4)

        # --- Anomaly check: negative or zero consumption ---
        anomalies = []
        if kwh_val is not None and kwh_val <= 0:
            anomalies.append('Zero or negative consumption — possible credit/reversal')
        if kwh_val is not None and kwh_val > 500_000:
            anomalies.append(f'Extremely high consumption ({kwh_val} kWh) — verify meter reading')

        results.append({
            'ok': len(errors) == 0,
            'row': row_num,
            'errors': errors,
            'anomalies': anomalies,
            'data': {
                'activity_date': activity_date,
                'period_start': period_start.date() if period_start else None,
                'period_end': period_end.date() if period_end else None,
                'scope': 2,
                'category': 'electricity',
                'original_quantity': float(kwh_val) if kwh_val else None,
                'original_unit': 'kWh',
                'quantity_kwh': float(kwh_val) if kwh_val else None,
                'emission_factor': ef,
                'emission_factor_source': ef_source,
                'emission_factor_unit': 'kgCO2e/kWh',
                'co2e_kg': co2e_kg,
                'metadata': {
                    'meter_id': norm.get('meter_id', ''),
                    'site_name': norm.get('site_name', ''),
                    'tariff': norm.get('tariff', ''),
                    'country': country,
                    'amount_gbp': norm.get('amount_gbp', ''),
                },
            },
            'raw': dict(row),
        })

    return results
