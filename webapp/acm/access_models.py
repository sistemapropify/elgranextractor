"""ACM-owned configuration and history; Propify identifiers are not Prometeo FKs."""
import uuid
from django.db import models


class ACMRolePolicy(models.Model):
    role_id = models.PositiveBigIntegerField(unique=True)
    permissions = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    updated_by = models.CharField(max_length=100)
    updated_at = models.DateTimeField(auto_now=True)


class ACMRoleAudit(models.Model):
    role_id = models.PositiveBigIntegerField(db_index=True)
    actor_id = models.CharField(max_length=100)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class ACMPortalAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.CharField(max_length=100, db_index=True)
    fingerprint = models.CharField(max_length=64)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner_id', 'fingerprint'], name='acm_owner_fingerprint_unique')]
        ordering = ['-created_at']

    @property
    def codigo_display(self):
        return 'ACM-' + self.id.hex[:10].upper()


class ACMPhotoReview(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    approved = models.BooleanField(default=False)
    reviewed_by = models.CharField(max_length=100)
    updated_at = models.DateTimeField(auto_now=True)
