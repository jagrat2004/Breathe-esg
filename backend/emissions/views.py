from django.db.models import Sum, Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EmissionRecord
from ingestion.serializers import EmissionRecordSerializer
from ingestion.views import get_tenant


class EmissionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        tenant = get_tenant(self.request)
        qs = EmissionRecord.objects.filter(tenant=tenant).select_related(
            'reviewed_by', 'source_batch', 'source_raw_row')

        # Filters
        scope = self.request.query_params.get('scope')
        if scope:
            qs = qs.filter(scope=scope)
        status_f = self.request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)
        source_type = self.request.query_params.get('source_type')
        if source_type:
            qs = qs.filter(source_type=source_type)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        anomaly = self.request.query_params.get('anomaly')
        if anomaly == 'true':
            qs = qs.filter(is_anomaly=True)
        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        record = self.get_object()
        if record.status == EmissionRecord.STATUS_LOCKED:
            return Response({'error': 'Record is locked for audit'}, status=400)
        note = request.data.get('note', '')
        record.approve(request.user, note)
        return Response({'status': 'approved', 'id': str(record.id)})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        record = self.get_object()
        if record.status == EmissionRecord.STATUS_LOCKED:
            return Response({'error': 'Record is locked for audit'}, status=400)
        note = request.data.get('note', '')
        record.reject(request.user, note)
        return Response({'status': 'rejected', 'id': str(record.id)})

    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        ids = request.data.get('ids', [])
        tenant = get_tenant(request)
        records = EmissionRecord.objects.filter(
            id__in=ids, tenant=tenant
        ).exclude(status=EmissionRecord.STATUS_LOCKED)
        count = 0
        for r in records:
            r.approve(request.user, note='Bulk approved')
            count += 1
        return Response({'approved': count})

    @action(detail=False, methods=['post'])
    def lock_approved(self, request):
        """Lock all approved records — sends them to audit state."""
        tenant = get_tenant(request)
        updated = EmissionRecord.objects.filter(
            tenant=tenant, status=EmissionRecord.STATUS_APPROVED
        ).update(status=EmissionRecord.STATUS_LOCKED)
        return Response({'locked': updated})


class DashboardView(APIView):
    def get(self, request):
        tenant = get_tenant(request)
        qs = EmissionRecord.objects.filter(tenant=tenant)

        total_co2e = qs.filter(co2e_kg__isnull=False).aggregate(t=Sum('co2e_kg'))['t'] or 0

        by_scope = {}
        for scope in [1, 2, 3]:
            val = qs.filter(scope=scope, co2e_kg__isnull=False).aggregate(t=Sum('co2e_kg'))['t'] or 0
            by_scope[f'scope_{scope}'] = round(float(val), 2)

        by_status = {}
        for s in EmissionRecord.STATUSES:
            by_status[s[0]] = qs.filter(status=s[0]).count()

        by_source = {}
        for src in ['sap', 'utility', 'travel']:
            val = qs.filter(source_type=src, co2e_kg__isnull=False).aggregate(t=Sum('co2e_kg'))['t'] or 0
            by_source[src] = round(float(val), 2)

        anomaly_count = qs.filter(is_anomaly=True).count()
        pending_count = qs.filter(status=EmissionRecord.STATUS_PENDING).count()
        flagged_count = qs.filter(status=EmissionRecord.STATUS_FLAGGED).count()

        # Monthly breakdown for chart
        from django.db.models.functions import TruncMonth
        monthly = (qs.filter(co2e_kg__isnull=False)
                   .annotate(month=TruncMonth('activity_date'))
                   .values('month', 'scope')
                   .annotate(total=Sum('co2e_kg'))
                   .order_by('month', 'scope'))

        monthly_data = {}
        for row in monthly:
            if row['month']:
                key = row['month'].strftime('%Y-%m')
                if key not in monthly_data:
                    monthly_data[key] = {'scope_1': 0, 'scope_2': 0, 'scope_3': 0}
                monthly_data[key][f"scope_{row['scope']}"] += float(row['total'])

        return Response({
            'total_co2e_kg': round(float(total_co2e), 2),
            'total_co2e_tonnes': round(float(total_co2e) / 1000, 3),
            'by_scope': by_scope,
            'by_source': by_source,
            'by_status': by_status,
            'anomaly_count': anomaly_count,
            'pending_count': pending_count,
            'flagged_count': flagged_count,
            'monthly_trend': monthly_data,
        })
