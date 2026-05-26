from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from ingestion.views import DataSourceViewSet, IngestionBatchViewSet, IngestView
from emissions.views import EmissionRecordViewSet, DashboardView

router = DefaultRouter()
router.register(r'data-sources', DataSourceViewSet, basename='datasource')
router.register(r'batches', IngestionBatchViewSet, basename='batch')
router.register(r'records', EmissionRecordViewSet, basename='record')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', obtain_auth_token),
    path('api/ingest/', IngestView.as_view()),
    path('api/dashboard/', DashboardView.as_view()),
    path('api/', include(router.urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
