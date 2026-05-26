from django.contrib import admin
from .models import Tenant, TenantUser
admin.site.register(Tenant)
admin.site.register(TenantUser)
