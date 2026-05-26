"""
SAP Fuel & Procurement Parser

Format chosen: SAP flat-file CSV export (transaction ME2M / MB51 style).
Justification: IDoc is XML-based and requires EDI middleware most clients
don't expose externally. OData (S/4HANA) needs live connectivity & OAuth.
Flat-file CSV is what sustainability teams actually email around — it's what
we see in practice for scoped ESG data pulls.

Real SAP exports often have:
  - German headers (Buchungsdatum, Menge, Einheit, Werk, Kostenstelle)
  - Mixed date formats (DD.MM.YYYY is standard in SAP)
  - Unit codes (L=litres, KG=kilograms, M3=cubic metres, KWH, TON)
  - Plant codes (4-char like "1000", "DE01")
  - Material numbers (18-char zero-padded like "000000000000500123")
  - Cost centre codes
  - Movement type codes (261=goods issue to production, 101=goods receipt)
"""

import csv
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

# SAP unit codes → canonical unit + conversion to kg or kWh
UNIT_MAP = {
    'L':   ('litres',        None),   # fuel: need fuel type to convert
    'LTR': ('litres',        None),
    'KG':  ('kg',            1.0),
    'G':   ('kg',            0.001),
    'TON': ('kg',            1000.0),
    'T':   ('kg',            1000.0),
    'M3':  ('m3',            None),   # gas: need density
    'KWH': ('kwh',           1.0),
    'MWH': ('kwh',           1000.0),
    'GJ':  ('kwh',           277.778),
}

# Fuel type → kgCO2e per litre (DEFRA 2023)
FUEL_EMISSION_FACTORS = {
    'diesel':        2.51,
    'petrol':        2.31,
    'lpg':           1.51,
    'natural_gas':   2.04,   # per kg
    'hfo':           3.17,   # heavy fuel oil per kg
}

# Movement types that represent actual consumption (not stock movements)
CONSUMPTION_MOVEMENT_TYPES = {'261', '201', '551', '601', '641'}

GERMAN_HEADER_MAP = {
    'Buchungsdatum':     'posting_date',
    'Belegdatum':        'document_date',
    'Menge':             'quantity',
    'Einheit':           'unit',
    'Werk':              'plant_code',
    'Kostenstelle':      'cost_center',
    'Materialnummer':    'material_number',
    'Materialbezeichnung': 'material_description',
    'Bewegungsart':      'movement_type',
    'Lieferant':         'vendor',
    'Betrag':            'amount',
    'Waehrung':          'currency',
    # English equivalents (SAP can export either)
    'Posting Date':      'posting_date',
    'Document Date':     'document_date',
    'Quantity':          'quantity',
    'Unit':              'unit',
    'Plant':             'plant_code',
    'Cost Center':       'cost_center',
    'Material':          'material_number',
    'Material Description': 'material_description',
    'Movement Type':     'movement_type',
    'Vendor':            'vendor',
    'Amount':            'amount',
    'Currency':          'currency',
}


def parse_sap_date(raw: str) -> Optional[datetime]:
    """SAP dates come as DD.MM.YYYY or YYYYMMDD or YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ('%d.%m.%Y', '%Y%m%d', '%Y-%m-%d', '%m/%d/%Y'):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def infer_fuel_type(material_desc: str) -> str:
    """Best-effort fuel type from material description."""
    desc = material_desc.lower()
    if any(w in desc for w in ['diesel', 'gas oil', 'gasoil']):
        return 'diesel'
    if any(w in desc for w in ['petrol', 'gasoline', 'benzin']):
        return 'petrol'
    if any(w in desc for w in ['lpg', 'propan', 'butan']):
        return 'lpg'
    if any(w in desc for w in ['natural gas', 'erdgas', 'methane']):
        return 'natural_gas'
    return 'diesel'  # conservative fallback — flagged as assumption


def parse_sap_csv(file_content: bytes) -> list[dict]:
    """
    Parse SAP flat-file export. Returns list of normalised row dicts.
    Each dict has: ok (bool), data (dict), errors (list of str).
    """
    results = []
    try:
        text = file_content.decode('utf-8', errors='replace')
    except Exception as e:
        return [{'ok': False, 'row': 0, 'data': {}, 'errors': [f'File decode error: {e}']}]

    reader = csv.DictReader(io.StringIO(text), delimiter=',')

    # Normalize headers using the German→English map
    raw_headers = reader.fieldnames or []
    header_map = {h: GERMAN_HEADER_MAP.get(h.strip(), h.strip().lower().replace(' ', '_'))
                  for h in raw_headers}

    for row_num, row in enumerate(reader, start=1):
        norm_row = {header_map.get(k, k): v.strip() if v else '' for k, v in row.items()}
        errors = []

        # --- Date ---
        date_raw = norm_row.get('posting_date') or norm_row.get('document_date', '')
        parsed_date = parse_sap_date(date_raw)
        if not parsed_date:
            errors.append(f"Cannot parse date: '{date_raw}'")

        # --- Quantity ---
        qty_raw = norm_row.get('quantity', '').replace(',', '.')  # SAP uses comma as decimal
        try:
            quantity = Decimal(qty_raw)
        except InvalidOperation:
            quantity = None
            errors.append(f"Cannot parse quantity: '{qty_raw}'")

        # --- Unit ---
        unit_raw = norm_row.get('unit', '').upper().strip()
        unit_info = UNIT_MAP.get(unit_raw)
        if not unit_info:
            errors.append(f"Unknown unit: '{unit_raw}'")

        # --- Movement type filter ---
        move_type = norm_row.get('movement_type', '').strip()
        if move_type and move_type not in CONSUMPTION_MOVEMENT_TYPES:
            # Not a consumption event — skip silently, not an error
            results.append({'ok': True, 'row': row_num, 'data': None,
                            'skipped': True, 'reason': f'movement_type {move_type} not consumption'})
            continue

        # --- Material / fuel type inference ---
        mat_desc = norm_row.get('material_description', '')
        fuel_type = infer_fuel_type(mat_desc)
        assumptions = []
        if not mat_desc:
            assumptions.append('fuel_type assumed diesel (no material description)')

        # --- CO2e calculation ---
        co2e_kg = None
        quantity_kg = None
        quantity_kwh = None
        ef = None
        ef_unit = None

        if quantity and unit_info:
            canon_unit, factor = unit_info
            ef_source = 'DEFRA 2023'

            if canon_unit == 'litres' and fuel_type in FUEL_EMISSION_FACTORS:
                ef = FUEL_EMISSION_FACTORS[fuel_type]
                ef_unit = 'kgCO2e/litre'
                co2e_kg = float(quantity) * ef
                quantity_kg = float(quantity) * 0.84  # approx litres→kg for diesel

            elif canon_unit == 'kg':
                quantity_kg = float(quantity) * factor
                if fuel_type in FUEL_EMISSION_FACTORS:
                    ef = FUEL_EMISSION_FACTORS[fuel_type]
                    ef_unit = 'kgCO2e/kg'
                    co2e_kg = quantity_kg * ef

            elif canon_unit == 'kwh':
                quantity_kwh = float(quantity) * factor
                # Electricity from SAP procurement = Scope 2
                ef = 0.233  # UK grid average DEFRA 2023
                ef_unit = 'kgCO2e/kWh'
                co2e_kg = quantity_kwh * ef

            elif canon_unit == 'm3':
                # Natural gas: 1 m3 ≈ 0.717 kg at STP
                quantity_kg = float(quantity) * 0.717
                ef = FUEL_EMISSION_FACTORS.get('natural_gas', 2.04)
                ef_unit = 'kgCO2e/kg'
                co2e_kg = quantity_kg * ef

        results.append({
            'ok': len(errors) == 0,
            'row': row_num,
            'errors': errors,
            'assumptions': assumptions,
            'data': {
                'activity_date': parsed_date.date() if parsed_date else None,
                'scope': 1,
                'category': 'fuel_combustion',
                'original_quantity': float(quantity) if quantity else None,
                'original_unit': unit_raw,
                'quantity_kg': quantity_kg,
                'quantity_kwh': quantity_kwh,
                'emission_factor': ef,
                'emission_factor_source': ef_source if ef else '',
                'emission_factor_unit': ef_unit or '',
                'co2e_kg': round(co2e_kg, 4) if co2e_kg else None,
                'metadata': {
                    'plant_code': norm_row.get('plant_code', ''),
                    'cost_center': norm_row.get('cost_center', ''),
                    'material_number': norm_row.get('material_number', '').lstrip('0'),
                    'material_description': mat_desc,
                    'movement_type': move_type,
                    'vendor': norm_row.get('vendor', ''),
                    'fuel_type': fuel_type,
                    'assumptions': assumptions,
                },
            },
            'raw': dict(row),
        })

    return results
