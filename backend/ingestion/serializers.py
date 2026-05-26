from rest_framework import serializers
from .models import DataSource, IngestionBatch, RawRow
from emissions.models import EmissionRecord


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'tenant']


class IngestionBatchSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source='data_source.get_source_type_display', read_only=True)
    data_source_name = serializers.CharField(source='data_source.name', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = ['id', 'data_source', 'data_source_name', 'source_type_display',
                  'filename', 'status', 'row_count', 'error_count',
                  'error_detail', 'created_at', 'processed_at']
        read_only_fields = ['id', 'status', 'row_count', 'error_count',
                            'error_detail', 'created_at', 'processed_at']


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'scope_display', 'category', 'category_display',
            'activity_date', 'period_start', 'period_end',
            'quantity_kwh', 'quantity_kg', 'quantity_km', 'quantity_nights',
            'original_unit', 'original_quantity',
            'emission_factor', 'emission_factor_source', 'emission_factor_unit',
            'co2e_kg', 'source_type', 'metadata',
            'status', 'status_display', 'reviewed_by', 'reviewed_by_name',
            'reviewed_at', 'review_note',
            'is_anomaly', 'anomaly_reasons',
            'is_edited', 'edit_history',
            'source_batch', 'source_raw_row',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'scope', 'category', 'source_type',
                            'source_batch', 'source_raw_row',
                            'created_at', 'updated_at', 'edit_history']

    def get_reviewed_by_name(self, obj):
        return obj.reviewed_by.get_full_name() or obj.reviewed_by.username if obj.reviewed_by else None
