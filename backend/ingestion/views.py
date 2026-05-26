import logging
from datetime import datetime
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, JSONParser

from .models import DataSource, IngestionBatch, RawRow
from .serializers import DataSourceSerializer, IngestionBatchSerializer, EmissionRecordSerializer
from .parsers.sap_parser import parse_sap_csv
from .parsers.utility_parser import parse_utility_csv
from .parsers.travel_parser import parse_travel_json
from emissions.models import EmissionRecord
from tenants.models import Tenant

logger = logging.getLogger(__name__)

ANOMALY_THRESHOLDS = {
    'co2e_kg': 100_000,  # 100 tonnes CO2e in a single record = likely error
}


def detect_anomalies(record_data: dict) -> list[str]:
    reasons = []
    co2e = record_data.get('co2e_kg')
    if co2e and co2e > ANOMALY_THRESHOLDS['co2e_kg']:
        reasons.append(f'Unusually high CO2e: {co2e:.0f} kg')
    if co2e and co2e < 0:
        reasons.append('Negative CO2e value')
    return reasons


class DataSourceViewSet(viewsets.ModelViewSet):
    serializer_class = DataSourceSerializer

    def get_queryset(self):
        tenant = get_tenant(self.request)
        return DataSource.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = get_tenant(self.request)
        serializer.save(tenant=tenant)


class IngestionBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionBatchSerializer

    def get_queryset(self):
        tenant = get_tenant(self.request)
        return IngestionBatch.objects.filter(data_source__tenant=tenant)


def get_tenant(request) -> Tenant:
    """Get or create a demo tenant for the authenticated user."""
    membership = request.user.tenant_memberships.select_related('tenant').first()
    if membership:
        return membership.tenant
    # Auto-create demo tenant
    tenant, _ = Tenant.objects.get_or_create(
        slug=f'demo-{request.user.username}',
        defaults={'name': f"{request.user.get_full_name() or request.user.username}'s Org"}
    )
    from tenants.models import TenantUser
    TenantUser.objects.get_or_create(tenant=tenant, user=request.user,
                                      defaults={'role': 'admin'})
    return tenant


class IngestView(APIView):
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        source_type = request.data.get('source_type')
        if source_type not in ('sap', 'utility', 'travel'):
            return Response({'error': 'source_type must be sap, utility, or travel'},
                            status=status.HTTP_400_BAD_REQUEST)

        tenant = get_tenant(request)
        source, _ = DataSource.objects.get_or_create(
            tenant=tenant, source_type=source_type,
            defaults={
                'name': f"{source_type.upper()} Source",
                'ingest_type': 'json_upload' if source_type == 'travel' else 'csv_upload',
            }
        )

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        content = file_obj.read()
        batch = IngestionBatch.objects.create(
            data_source=source,
            uploaded_by=request.user,
            filename=file_obj.name,
            status=IngestionBatch.STATUS_PROCESSING,
        )

        # Run the appropriate parser
        country = request.data.get('country', 'UK')
        if source_type == 'sap':
            rows = parse_sap_csv(content)
        elif source_type == 'utility':
            rows = parse_utility_csv(content, country=country)
        else:
            rows = parse_travel_json(content)

        created = 0
        errors = 0
        error_msgs = []

        for row_result in rows:
            raw = RawRow.objects.create(
                batch=batch,
                row_number=row_result['row'],
                raw_data=row_result.get('raw', {}),
                parse_error='\n'.join(row_result.get('errors', [])),
            )

            if row_result.get('skipped'):
                continue

            if not row_result['ok'] or not row_result.get('data'):
                errors += 1
                error_msgs.append(f"Row {row_result['row']}: {'; '.join(row_result.get('errors', []))}")
                continue

            d = row_result['data']
            if not d.get('activity_date'):
                errors += 1
                error_msgs.append(f"Row {row_result['row']}: No activity date")
                continue

            anomaly_reasons = detect_anomalies(d) + row_result.get('anomalies', [])

            rec = EmissionRecord.objects.create(
                tenant=tenant,
                source_batch=batch,
                source_raw_row=raw,
                source_type=source_type,
                scope=d['scope'],
                category=d['category'],
                activity_date=d['activity_date'],
                period_start=d.get('period_start'),
                period_end=d.get('period_end'),
                quantity_kwh=d.get('quantity_kwh'),
                quantity_kg=d.get('quantity_kg'),
                quantity_km=d.get('quantity_km'),
                quantity_nights=d.get('quantity_nights'),
                original_unit=d.get('original_unit', ''),
                original_quantity=d.get('original_quantity'),
                emission_factor=d.get('emission_factor'),
                emission_factor_source=d.get('emission_factor_source', ''),
                emission_factor_unit=d.get('emission_factor_unit', ''),
                co2e_kg=d.get('co2e_kg'),
                metadata=d.get('metadata', {}),
                status=EmissionRecord.STATUS_FLAGGED if anomaly_reasons else EmissionRecord.STATUS_PENDING,
                is_anomaly=bool(anomaly_reasons),
                anomaly_reasons=anomaly_reasons,
            )
            created += 1

        batch.status = IngestionBatch.STATUS_DONE
        batch.row_count = created
        batch.error_count = errors
        batch.error_detail = '\n'.join(error_msgs[:20])
        batch.processed_at = timezone.now()
        batch.save()

        return Response({
            'batch_id': str(batch.id),
            'created': created,
            'errors': errors,
            'error_detail': error_msgs[:10],
        }, status=status.HTTP_201_CREATED)
