"""
Corporate Travel Parser

Format chosen: JSON export (Concur / Navan API style).
Justification:
  - Concur Travel & Expense exposes a REST API returning JSON trip segments.
  - Navan (formerly TripActions) similarly offers webhook + REST JSON.
  - These are the two dominant enterprise travel platforms (covering ~60% of 
    Fortune 500). A JSON upload simulates an API pull without requiring live 
    OAuth credentials — in production you'd schedule a pull job.
  - CSV exports from these platforms exist but lose structured segment nesting
    (a single trip has flight + hotel + car segments).

Key complexity:
  - Flights: often only origin/destination IATA codes given, no distance.
    We use a great-circle distance lookup table for common routes.
  - Hotels: emission factor is per room-night.
  - Ground: emission factor varies by transport type (taxi, rail, car hire).
  - Cabin class multiplier: business class ≈ 2.9× economy (DEFRA 2023).
  - All = Scope 3 (Category 6: Business Travel).
"""

import json
import logging
import math
from datetime import datetime
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

# Flight emission factors kgCO2e/km per passenger (DEFRA 2023, includes RFI factor)
FLIGHT_EF = {
    'economy':        0.1553,
    'premium_economy': 0.2427,
    'business':       0.4290,
    'first':          0.5765,
}

# Approximate IATA airport coordinates for distance calculation
# (subset of high-traffic airports; production would use a full DB table)
AIRPORT_COORDS = {
    'LHR': (51.477, -0.461),   'LGW': (51.148, -0.190),
    'CDG': (49.009, 2.547),    'AMS': (52.310, 4.768),
    'FRA': (50.033, 8.571),    'MUC': (48.354, 11.786),
    'MAD': (40.472, -3.560),   'BCN': (41.297, 2.078),
    'JFK': (40.640, -73.779),  'LAX': (33.943, -118.408),
    'ORD': (41.974, -87.907),  'SFO': (37.619, -122.375),
    'DXB': (25.253, 55.364),   'SIN': (1.350, 103.994),
    'HKG': (22.309, 113.915),  'NRT': (35.765, 140.386),
    'BOM': (19.089, 72.868),   'DEL': (28.556, 77.100),
    'SYD': (33.947, 151.177),  'DOH': (25.261, 51.565),
    'IST': (41.275, 28.752),   'ZRH': (47.458, 8.548),
    'GVA': (46.238, 6.109),    'CPH': (55.618, 12.656),
    'BRU': (50.902, 4.484),    'VIE': (48.110, 16.570),
    'DUB': (53.421, -6.270),   'MAN': (53.354, -2.275),
}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def flight_distance_km(origin: str, dest: str) -> Optional[float]:
    o = AIRPORT_COORDS.get(origin.upper())
    d = AIRPORT_COORDS.get(dest.upper())
    if o and d:
        return haversine_km(*o, *d)
    return None


# Ground transport factors kgCO2e/km
GROUND_EF = {
    'taxi':          0.1489,
    'car_hire':      0.1686,
    'rental_car':    0.1686,
    'rail':          0.0035,
    'train':         0.0035,
    'bus':           0.0273,
    'subway':        0.0028,
    'rideshare':     0.1489,
    'default':       0.1686,
}

# Hotel: kgCO2e per room-night (DEFRA 2023 average)
HOTEL_EF_PER_NIGHT = {
    'UK':      20.8,
    'US':      31.2,
    'DE':      18.4,
    'FR':      15.7,
    'DEFAULT': 20.8,
}


def parse_travel_json(file_content: bytes) -> list[dict]:
    """
    Parse Concur/Navan-style JSON trip export.
    
    Expected top-level structure:
    {
      "trips": [
        {
          "trip_id": "...",
          "traveler_id": "...",
          "traveler_name": "...",
          "segments": [
            {"type": "flight", "origin": "LHR", "destination": "JFK",
             "departure_date": "2024-03-15", "cabin_class": "economy", ...},
            {"type": "hotel", "check_in": "2024-03-15", "check_out": "2024-03-18",
             "country": "US", ...},
            {"type": "ground", "transport_type": "taxi", "distance_km": 45,
             "date": "2024-03-15", ...}
          ]
        }
      ]
    }
    """
    results = []
    try:
        payload = json.loads(file_content.decode('utf-8', errors='replace'))
    except json.JSONDecodeError as e:
        return [{'ok': False, 'row': 0, 'data': {}, 'errors': [f'JSON parse error: {e}']}]

    trips = payload if isinstance(payload, list) else payload.get('trips', [])
    row_num = 0

    for trip in trips:
        trip_id = trip.get('trip_id', '')
        traveler_id = trip.get('traveler_id', '')
        traveler_name = trip.get('traveler_name', '')
        segments = trip.get('segments', [])

        for segment in segments:
            row_num += 1
            seg_type = segment.get('type', '').lower()
            errors = []
            anomalies = []
            data = None

            if seg_type == 'flight':
                origin = segment.get('origin', '').upper()
                dest = segment.get('destination', '').upper()
                cabin = segment.get('cabin_class', 'economy').lower()
                date_raw = segment.get('departure_date', '')

                dep_date = None
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
                    try:
                        dep_date = datetime.strptime(date_raw, fmt).date()
                        break
                    except ValueError:
                        continue
                if not dep_date:
                    errors.append(f"Cannot parse departure_date: '{date_raw}'")

                # Distance
                dist_km = segment.get('distance_km') or flight_distance_km(origin, dest)
                assumptions = []
                if not segment.get('distance_km') and dist_km:
                    assumptions.append(f'distance_km computed via haversine ({origin}→{dest})')
                if not dist_km:
                    errors.append(f'Cannot compute distance for {origin}→{dest} (airports not in lookup)')

                ef = FLIGHT_EF.get(cabin, FLIGHT_EF['economy'])
                co2e_kg = round(dist_km * ef, 4) if dist_km else None

                data = {
                    'activity_date': dep_date,
                    'scope': 3,
                    'category': 'flight',
                    'original_quantity': dist_km,
                    'original_unit': 'km',
                    'quantity_km': dist_km,
                    'emission_factor': ef,
                    'emission_factor_source': 'DEFRA 2023',
                    'emission_factor_unit': 'kgCO2e/km/pax',
                    'co2e_kg': co2e_kg,
                    'metadata': {
                        'trip_id': trip_id, 'traveler_id': traveler_id,
                        'traveler_name': traveler_name,
                        'origin': origin, 'destination': dest,
                        'cabin_class': cabin, 'assumptions': assumptions,
                    },
                }
                if co2e_kg and co2e_kg > 5000:
                    anomalies.append(f'Very high flight emission ({co2e_kg} kg) — verify distance/class')

            elif seg_type == 'hotel':
                check_in_raw = segment.get('check_in', '')
                check_out_raw = segment.get('check_out', '')
                country = segment.get('country', 'DEFAULT').upper()

                ci = co = None
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        ci = datetime.strptime(check_in_raw, fmt).date()
                        break
                    except ValueError:
                        continue
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        co = datetime.strptime(check_out_raw, fmt).date()
                        break
                    except ValueError:
                        continue

                if not ci:
                    errors.append(f"Cannot parse check_in: '{check_in_raw}'")
                if not co:
                    errors.append(f"Cannot parse check_out: '{check_out_raw}'")

                nights = (co - ci).days if ci and co else None
                if nights is not None and nights <= 0:
                    errors.append('check_out must be after check_in')

                ef = HOTEL_EF_PER_NIGHT.get(country, HOTEL_EF_PER_NIGHT['DEFAULT'])
                co2e_kg = round(nights * ef, 4) if nights else None

                data = {
                    'activity_date': ci,
                    'period_start': ci,
                    'period_end': co,
                    'scope': 3,
                    'category': 'hotel',
                    'original_quantity': nights,
                    'original_unit': 'nights',
                    'quantity_nights': nights,
                    'emission_factor': ef,
                    'emission_factor_source': 'DEFRA 2023',
                    'emission_factor_unit': 'kgCO2e/room-night',
                    'co2e_kg': co2e_kg,
                    'metadata': {
                        'trip_id': trip_id, 'traveler_id': traveler_id,
                        'traveler_name': traveler_name,
                        'country': country,
                        'hotel_name': segment.get('hotel_name', ''),
                    },
                }

            elif seg_type in ('ground', 'car', 'taxi', 'rail', 'train', 'bus'):
                transport_type = segment.get('transport_type', seg_type).lower()
                dist_km = segment.get('distance_km')
                date_raw = segment.get('date', '')

                act_date = None
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        act_date = datetime.strptime(date_raw, fmt).date()
                        break
                    except ValueError:
                        continue
                if not act_date:
                    errors.append(f"Cannot parse date: '{date_raw}'")
                if not dist_km:
                    errors.append('distance_km required for ground transport')

                ef = GROUND_EF.get(transport_type, GROUND_EF['default'])
                co2e_kg = round(float(dist_km) * ef, 4) if dist_km else None

                data = {
                    'activity_date': act_date,
                    'scope': 3,
                    'category': 'ground_transport',
                    'original_quantity': float(dist_km) if dist_km else None,
                    'original_unit': 'km',
                    'quantity_km': float(dist_km) if dist_km else None,
                    'emission_factor': ef,
                    'emission_factor_source': 'DEFRA 2023',
                    'emission_factor_unit': 'kgCO2e/km',
                    'co2e_kg': co2e_kg,
                    'metadata': {
                        'trip_id': trip_id, 'traveler_id': traveler_id,
                        'traveler_name': traveler_name,
                        'transport_type': transport_type,
                    },
                }
            else:
                errors.append(f"Unknown segment type: '{seg_type}'")

            results.append({
                'ok': len(errors) == 0 and data is not None,
                'row': row_num,
                'errors': errors,
                'anomalies': anomalies if 'anomalies' in dir() else [],
                'data': data,
                'raw': segment,
            })

    return results
