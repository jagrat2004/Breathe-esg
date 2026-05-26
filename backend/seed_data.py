"""
Seed script: creates demo user + realistic sample data for all 3 sources.
Run: python seed_data.py
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from tenants.models import Tenant, TenantUser
from ingestion.models import DataSource, IngestionBatch, RawRow
from emissions.models import EmissionRecord
from datetime import date, timedelta
import random

# Create demo users
analyst, _ = User.objects.get_or_create(username='analyst', defaults={
    'email': 'analyst@demo.com', 'first_name': 'Alex', 'last_name': 'Chen'})
analyst.set_password('demo1234')
analyst.save()
Token.objects.get_or_create(user=analyst)

admin_user, _ = User.objects.get_or_create(username='admin', defaults={
    'email': 'admin@demo.com', 'first_name': 'Sam', 'last_name': 'Patel',
    'is_staff': True, 'is_superuser': True})
admin_user.set_password('admin1234')
admin_user.save()
Token.objects.get_or_create(user=admin_user)

# Create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='acme-corp',
    defaults={'name': 'Acme Manufacturing Ltd'}
)
TenantUser.objects.get_or_create(tenant=tenant, user=analyst, defaults={'role': 'analyst'})
TenantUser.objects.get_or_create(tenant=tenant, user=admin_user, defaults={'role': 'admin'})

# Create data sources
sap_src, _ = DataSource.objects.get_or_create(tenant=tenant, source_type='sap',
    defaults={'name': 'SAP ECC Fuel & Procurement', 'ingest_type': 'csv_upload'})
util_src, _ = DataSource.objects.get_or_create(tenant=tenant, source_type='utility',
    defaults={'name': 'EDF Portal CSV Export', 'ingest_type': 'csv_upload'})
travel_src, _ = DataSource.objects.get_or_create(tenant=tenant, source_type='travel',
    defaults={'name': 'Navan JSON Export', 'ingest_type': 'json_upload'})

batch_sap = IngestionBatch.objects.create(data_source=sap_src, uploaded_by=analyst,
    filename='MB51_Q1_2024.csv', status='done', row_count=12, error_count=1)
batch_util = IngestionBatch.objects.create(data_source=util_src, uploaded_by=analyst,
    filename='EDF_billing_Q1_2024.csv', status='done', row_count=6, error_count=0)
batch_travel = IngestionBatch.objects.create(data_source=travel_src, uploaded_by=analyst,
    filename='navan_trips_Q1_2024.json', status='done', row_count=18, error_count=2)

def make_raw(batch, n, data):
    return RawRow.objects.create(batch=batch, row_number=n, raw_data=data)

# --- SAP Scope 1 records (fuel combustion) ---
sap_records = [
    {'date': date(2024,1,15), 'qty_kg': 4800, 'fuel': 'diesel', 'plant': '1000', 'cc': 'CC-1001', 'mat': 'Diesel Fuel (Gasoil)', 'co2e': 12048.0},
    {'date': date(2024,1,22), 'qty_kg': 3200, 'fuel': 'diesel', 'plant': '1000', 'cc': 'CC-1001', 'mat': 'Diesel Fuel (Gasoil)', 'co2e': 8032.0},
    {'date': date(2024,2,5),  'qty_kg': 5100, 'fuel': 'diesel', 'plant': '2000', 'cc': 'CC-2003', 'mat': 'Diesel Fuel (Gasoil)', 'co2e': 12801.0},
    {'date': date(2024,2,18), 'qty_kg': 2100, 'fuel': 'petrol', 'plant': '1000', 'cc': 'CC-1005', 'mat': 'Petrol/Gasoline (Benzin)', 'co2e': 4851.0},
    {'date': date(2024,3,1),  'qty_kg': 8900, 'fuel': 'diesel', 'plant': '2000', 'cc': 'CC-2003', 'mat': 'Diesel Fuel (Gasoil)', 'co2e': 22339.0},
    {'date': date(2024,3,12), 'qty_kg': 1500, 'fuel': 'lpg',    'plant': '3000', 'cc': 'CC-3001', 'mat': 'LPG (Propan)', 'co2e': 2265.0},
    # anomaly — very high
    {'date': date(2024,2,28), 'qty_kg': 45000, 'fuel': 'diesel', 'plant': '1000', 'cc': 'CC-1001', 'mat': 'Diesel Fuel (Gasoil)', 'co2e': 112950.0, 'anomaly': True},
]

statuses = ['approved', 'approved', 'pending', 'pending', 'pending', 'approved', 'flagged']
for i, r in enumerate(sap_records):
    raw = make_raw(batch_sap, i+1, {'Buchungsdatum': str(r['date']), 'Menge': r['qty_kg'],
        'Einheit': 'KG', 'Werk': r['plant'], 'Kostenstelle': r['cc'],
        'Materialbezeichnung': r['mat'], 'Bewegungsart': '261'})
    is_anomaly = r.get('anomaly', False)
    rec = EmissionRecord.objects.create(
        tenant=tenant, source_batch=batch_sap, source_raw_row=raw,
        source_type='sap', scope=1, category='fuel_combustion',
        activity_date=r['date'],
        quantity_kg=r['qty_kg'], original_quantity=r['qty_kg'], original_unit='KG',
        emission_factor=2.51, emission_factor_source='DEFRA 2023',
        emission_factor_unit='kgCO2e/kg',
        co2e_kg=r['co2e'],
        metadata={'plant_code': r['plant'], 'cost_center': r['cc'],
                  'material_description': r['mat'], 'fuel_type': r['fuel'],
                  'movement_type': '261'},
        status=statuses[i], is_anomaly=is_anomaly,
        anomaly_reasons=['Unusually high CO2e: 112950 kg'] if is_anomaly else [],
    )
    if statuses[i] == 'approved':
        rec.reviewed_by = analyst
        rec.reviewed_at = rec.created_at
        rec.save()

# --- Utility Scope 2 records ---
util_records = [
    {'start': date(2024,1,1), 'end': date(2024,1,31), 'kwh': 48200, 'meter': 'MTR-001', 'site': 'Factory A, Manchester'},
    {'start': date(2024,2,1), 'end': date(2024,2,29), 'kwh': 41800, 'meter': 'MTR-001', 'site': 'Factory A, Manchester'},
    {'start': date(2024,3,1), 'end': date(2024,3,31), 'kwh': 52100, 'meter': 'MTR-001', 'site': 'Factory A, Manchester'},
    {'start': date(2024,1,17), 'end': date(2024,2,14), 'kwh': 12300, 'meter': 'MTR-002', 'site': 'Office HQ, London'},
    {'start': date(2024,2,15), 'end': date(2024,3,14), 'kwh': 11800, 'meter': 'MTR-002', 'site': 'Office HQ, London'},
    {'start': date(2024,3,15), 'end': date(2024,4,14), 'kwh': 13200, 'meter': 'MTR-002', 'site': 'Office HQ, London'},
]

util_statuses = ['approved', 'approved', 'pending', 'approved', 'pending', 'pending']
for i, r in enumerate(util_records):
    mid = r['start'] + (r['end'] - r['start']) / 2
    raw = make_raw(batch_util, i+1, {'period_start': str(r['start']), 'period_end': str(r['end']),
        'consumption_kwh': r['kwh'], 'meter_id': r['meter'], 'site': r['site']})
    co2e = round(r['kwh'] * 0.2128, 4)
    rec = EmissionRecord.objects.create(
        tenant=tenant, source_batch=batch_util, source_raw_row=raw,
        source_type='utility', scope=2, category='electricity',
        activity_date=mid, period_start=r['start'], period_end=r['end'],
        quantity_kwh=r['kwh'], original_quantity=r['kwh'], original_unit='kWh',
        emission_factor=0.2128, emission_factor_source='DEFRA 2023',
        emission_factor_unit='kgCO2e/kWh', co2e_kg=co2e,
        metadata={'meter_id': r['meter'], 'site_name': r['site'], 'country': 'UK', 'tariff': 'HH-Metered'},
        status=util_statuses[i],
    )
    if util_statuses[i] == 'approved':
        rec.reviewed_by = analyst
        rec.reviewed_at = rec.created_at
        rec.save()

# --- Travel Scope 3 records ---
travel_records = [
    # Flights
    {'cat': 'flight', 'date': date(2024,1,10), 'km': 5541, 'ef': 0.1553, 'cabin': 'economy',
     'meta': {'origin': 'LHR', 'destination': 'JFK', 'traveler_name': 'Alice Johnson',
               'traveler_id': 'EMP-042', 'trip_id': 'TRIP-2401-001'}},
    {'cat': 'flight', 'date': date(2024,1,10), 'km': 5541, 'ef': 0.4290, 'cabin': 'business',
     'meta': {'origin': 'LHR', 'destination': 'JFK', 'traveler_name': 'Bob Williams',
               'traveler_id': 'EMP-017', 'trip_id': 'TRIP-2401-002'}},
    {'cat': 'flight', 'date': date(2024,2,14), 'km': 932, 'ef': 0.1553, 'cabin': 'economy',
     'meta': {'origin': 'LHR', 'destination': 'CDG', 'traveler_name': 'Alice Johnson',
               'traveler_id': 'EMP-042', 'trip_id': 'TRIP-2402-001'}},
    {'cat': 'flight', 'date': date(2024,3,5), 'km': 1892, 'ef': 0.1553, 'cabin': 'economy',
     'meta': {'origin': 'LHR', 'destination': 'DXB', 'traveler_name': 'Carol Smith',
               'traveler_id': 'EMP-089', 'trip_id': 'TRIP-2403-001'}},
    # Hotels
    {'cat': 'hotel', 'date': date(2024,1,10), 'nights': 4, 'ef': 31.2,
     'meta': {'hotel_name': 'Marriott Times Square', 'country': 'US',
               'traveler_name': 'Alice Johnson', 'traveler_id': 'EMP-042', 'trip_id': 'TRIP-2401-001'}},
    {'cat': 'hotel', 'date': date(2024,1,10), 'nights': 4, 'ef': 31.2,
     'meta': {'hotel_name': 'Marriott Times Square', 'country': 'US',
               'traveler_name': 'Bob Williams', 'traveler_id': 'EMP-017', 'trip_id': 'TRIP-2401-002'}},
    {'cat': 'hotel', 'date': date(2024,2,14), 'nights': 2, 'ef': 15.7,
     'meta': {'hotel_name': 'Novotel Paris Centre', 'country': 'FR',
               'traveler_name': 'Alice Johnson', 'traveler_id': 'EMP-042', 'trip_id': 'TRIP-2402-001'}},
    # Ground
    {'cat': 'ground_transport', 'date': date(2024,1,10), 'km': 45, 'ef': 0.1489,
     'meta': {'transport_type': 'taxi', 'traveler_name': 'Alice Johnson',
               'traveler_id': 'EMP-042', 'trip_id': 'TRIP-2401-001'}},
    {'cat': 'ground_transport', 'date': date(2024,2,14), 'km': 380, 'ef': 0.0035,
     'meta': {'transport_type': 'rail', 'traveler_name': 'David Lee',
               'traveler_id': 'EMP-055', 'trip_id': 'TRIP-2402-002'}},
]

travel_statuses = ['approved', 'flagged', 'pending', 'pending', 'approved', 'pending', 'pending', 'approved', 'pending']
for i, r in enumerate(travel_records):
    cat = r['cat']
    raw_data = dict(r['meta'])
    raw_data.update({'type': cat, 'date': str(r['date'])})
    raw = make_raw(batch_travel, i+1, raw_data)

    if cat == 'flight':
        qty_km = r['km']
        co2e = round(qty_km * r['ef'], 4)
        is_anomaly = co2e > 5000
        rec = EmissionRecord.objects.create(
            tenant=tenant, source_batch=batch_travel, source_raw_row=raw,
            source_type='travel', scope=3, category=cat,
            activity_date=r['date'],
            quantity_km=qty_km, original_quantity=qty_km, original_unit='km',
            emission_factor=r['ef'], emission_factor_source='DEFRA 2023',
            emission_factor_unit='kgCO2e/km/pax', co2e_kg=co2e,
            metadata={**r['meta'], 'cabin_class': r.get('cabin', 'economy')},
            status=travel_statuses[i],
            is_anomaly=is_anomaly,
            anomaly_reasons=[f'High flight CO2e ({co2e:.0f} kg) - business class LHR-JFK'] if is_anomaly else [],
        )
    elif cat == 'hotel':
        nights = r['nights']
        co2e = round(nights * r['ef'], 4)
        rec = EmissionRecord.objects.create(
            tenant=tenant, source_batch=batch_travel, source_raw_row=raw,
            source_type='travel', scope=3, category=cat,
            activity_date=r['date'],
            quantity_nights=nights, original_quantity=nights, original_unit='nights',
            emission_factor=r['ef'], emission_factor_source='DEFRA 2023',
            emission_factor_unit='kgCO2e/room-night', co2e_kg=co2e,
            metadata=r['meta'],
            status=travel_statuses[i],
        )
    else:
        qty_km = r['km']
        co2e = round(qty_km * r['ef'], 4)
        rec = EmissionRecord.objects.create(
            tenant=tenant, source_batch=batch_travel, source_raw_row=raw,
            source_type='travel', scope=3, category=cat,
            activity_date=r['date'],
            quantity_km=qty_km, original_quantity=qty_km, original_unit='km',
            emission_factor=r['ef'], emission_factor_source='DEFRA 2023',
            emission_factor_unit='kgCO2e/km', co2e_kg=co2e,
            metadata=r['meta'],
            status=travel_statuses[i],
        )

    if travel_statuses[i] == 'approved':
        rec.reviewed_by = analyst
        rec.reviewed_at = rec.created_at
        rec.save()

print("✅ Seed data created successfully!")
print(f"   Analyst login: analyst / demo1234")
print(f"   Admin login:   admin / admin1234")
print(f"   Tenant: {tenant.name}")
print(f"   Records: {EmissionRecord.objects.filter(tenant=tenant).count()}")
