from django.contrib import admin
from .models import EmissionRecord

@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'tenant', 'scope', 'category', 'activity_date', 'co2e_kg', 'status', 'is_anomaly']
    list_filter = ['scope', 'status', 'source_type', 'is_anomaly']
    search_fields = ['metadata__plant_code', 'metadata__meter_id', 'metadata__trip_id']
