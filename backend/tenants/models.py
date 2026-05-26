from django.db import models
import uuid


class Tenant(models.Model):
    """
    Multi-tenant isolation unit. Every data row is scoped to a tenant.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TenantUser(models.Model):
    """Links Django users to tenants with roles."""
    ROLE_ANALYST = 'analyst'
    ROLE_ADMIN = 'admin'
    ROLE_AUDITOR = 'auditor'
    ROLES = [
        (ROLE_ANALYST, 'Analyst'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_AUDITOR, 'Auditor'),
    ]

    from django.contrib.auth.models import User
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='tenant_memberships')
    role = models.CharField(max_length=20, choices=ROLES, default=ROLE_ANALYST)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'user')

    def __str__(self):
        return f"{self.user.username} @ {self.tenant.name} ({self.role})"
