from django.contrib import admin
from .models import DataSource, IngestionBatch, RawRow

admin.site.register(DataSource)
admin.site.register(IngestionBatch)
admin.site.register(RawRow)
