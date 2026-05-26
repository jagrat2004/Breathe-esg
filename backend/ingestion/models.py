from django.db import models
import uuid


class DataSource(models.Model):
    """
    Represents a configured ingestion source for a tenant.
    Tracks provenance: which system produced a batch of rows.
    """
    SOURCE_SAP = 'sap'
    SOURCE_UTILITY = 'utility'
    SOURCE_TRAVEL = 'travel'
    SOURCE_TYPES = [
        (SOURCE_SAP, 'SAP Fuel & Procurement'),
        (SOURCE_UTILITY, 'Utility / Electricity'),
        (SOURCE_TRAVEL, 'Corporate Travel'),
    ]

    INGEST_CSV = 'csv_upload'
    INGEST_PDF = 'pdf_upload'
    INGEST_JSON = 'json_upload'
    INGEST_TYPES = [
        (INGEST_CSV, 'CSV File Upload'),
        (INGEST_PDF, 'PDF Upload'),
        (INGEST_JSON, 'JSON / API Payload'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='data_sources')
    name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    ingest_type = models.CharField(max_length=20, choices=INGEST_TYPES, default=INGEST_CSV)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tenant.name} – {self.get_source_type_display()}"


class IngestionBatch(models.Model):
    """
    One upload / pull event. Groups raw rows and tracks status lifecycle.
    This is the source-of-truth record: what came in, when, from where.
    """
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUSES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='batches')
    uploaded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    filename = models.CharField(max_length=512, blank=True)
    raw_file = models.FileField(upload_to='raw_uploads/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_PENDING)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Batch {self.id} – {self.data_source} [{self.status}]"


class RawRow(models.Model):
    """
    Immutable copy of a single raw record from a batch.
    Never mutated after creation — edit audit lives on EmissionRecord.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='raw_rows')
    row_number = models.IntegerField()
    raw_data = models.JSONField()  # exact original fields
    parse_error = models.TextField(blank=True)  # set if this row failed parsing
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['row_number']

    def __str__(self):
        return f"Row {self.row_number} of batch {self.batch_id}"
