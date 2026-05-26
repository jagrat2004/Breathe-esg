from django.db import models
from django.contrib.postgres.fields import ArrayField
import uuid
from decimal import Decimal


class EmissionRecord(models.Model):
    """
    Core normalized emission record. ONE row per activity event after normalization.

    Scope classification:
      Scope 1 – Direct combustion (fuel from SAP)
      Scope 2 – Purchased electricity (utility data)
      Scope 3 – Value chain / travel (corporate travel)

    Units are ALWAYS normalized to:
      - quantity_kwh  for energy
      - quantity_kg   for mass
      - quantity_km   for distance
      - co2e_kg       for emissions (the canonical output)

    Source-of-truth fields track lineage completely.
    """
    SCOPE_1 = 1
    SCOPE_2 = 2
    SCOPE_3 = 3
    SCOPES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]

    CATEGORY_FUEL = 'fuel_combustion'
    CATEGORY_ELECTRICITY = 'electricity'
    CATEGORY_FLIGHT = 'flight'
    CATEGORY_HOTEL = 'hotel'
    CATEGORY_GROUND = 'ground_transport'
    CATEGORY_PROCUREMENT = 'procurement'
    CATEGORIES = [
        (CATEGORY_FUEL, 'Fuel Combustion'),
        (CATEGORY_ELECTRICITY, 'Electricity'),
        (CATEGORY_FLIGHT, 'Flight'),
        (CATEGORY_HOTEL, 'Hotel Stay'),
        (CATEGORY_GROUND, 'Ground Transport'),
        (CATEGORY_PROCUREMENT, 'Procurement'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_FLAGGED = 'flagged'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_LOCKED = 'locked'   # locked after auditor sign-off
    STATUSES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_FLAGGED, 'Flagged'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_LOCKED, 'Locked for Audit'),
    ]

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='emission_records')

    # Provenance — immutable after creation
    source_batch = models.ForeignKey('ingestion.IngestionBatch', on_delete=models.SET_NULL,
                                     null=True, related_name='emission_records')
    source_raw_row = models.ForeignKey('ingestion.RawRow', on_delete=models.SET_NULL,
                                       null=True, related_name='emission_record')
    source_type = models.CharField(max_length=20)  # mirrors DataSource.source_type

    # Scope & category
    scope = models.IntegerField(choices=SCOPES)
    category = models.CharField(max_length=30, choices=CATEGORIES)

    # Activity period
    activity_date = models.DateField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    # Normalized quantity fields (only relevant ones are filled per category)
    quantity_kwh = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    quantity_kg = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    quantity_km = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    quantity_nights = models.IntegerField(null=True, blank=True)  # for hotels
    original_unit = models.CharField(max_length=50, blank=True)
    original_quantity = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    # Emission factor applied
    emission_factor = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    emission_factor_source = models.CharField(max_length=255, blank=True)  # e.g. "DEFRA 2023"
    emission_factor_unit = models.CharField(max_length=50, blank=True)  # e.g. "kgCO2e/kWh"

    # Final output
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    # Source-specific metadata (flexible, varies by source type)
    metadata = models.JSONField(default=dict)
    # For SAP: plant_code, cost_center, material_number, vendor
    # For utility: meter_id, tariff, billing_period
    # For travel: trip_id, origin, destination, traveler_id, transport_class

    # Analyst review fields
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='reviewed_records')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    # Anomaly / flag fields
    is_anomaly = models.BooleanField(default=False)
    anomaly_reasons = models.JSONField(default=list)  # list of strings

    # Edit audit trail — was this record manually corrected after ingestion?
    is_edited = models.BooleanField(default=False)
    edit_history = models.JSONField(default=list)  # list of {field, old_val, new_val, user, ts}

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['tenant', 'scope', 'status']),
            models.Index(fields=['tenant', 'activity_date']),
            models.Index(fields=['source_batch']),
        ]

    def __str__(self):
        return f"{self.get_category_display()} | {self.co2e_kg} kgCO2e | {self.activity_date}"

    def approve(self, user, note=''):
        from django.utils import timezone
        self.status = self.STATUS_APPROVED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_note = note
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])

    def reject(self, user, note=''):
        from django.utils import timezone
        self.status = self.STATUS_REJECTED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_note = note
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])

    def flag(self, reasons: list):
        self.is_anomaly = True
        self.anomaly_reasons = reasons
        self.status = self.STATUS_FLAGGED
        self.save(update_fields=['is_anomaly', 'anomaly_reasons', 'status', 'updated_at'])

    def record_edit(self, user, field, old_val, new_val):
        from django.utils import timezone
        self.edit_history.append({
            'field': field,
            'old_value': str(old_val),
            'new_value': str(new_val),
            'edited_by': user.username,
            'edited_at': timezone.now().isoformat(),
        })
        self.is_edited = True
        setattr(self, field, new_val)
        self.save()
