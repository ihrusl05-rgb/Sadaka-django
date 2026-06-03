from django.apps import apps
from django.conf import settings
from django.db import connections
from django.db.models import Count
from drf_spectacular.utils import extend_schema
from redis import Redis
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from common.api.serializers import HealthcheckSerializer, PlatformAnalyticsSerializer
from common.permissions import IsPlatformAdmin
from apps.platform.models import AuditLog


class HealthcheckView(APIView):
    permission_classes = []
    authentication_classes = []
    serializer_class = HealthcheckSerializer

    @extend_schema(responses=HealthcheckSerializer, tags=["System"])
    def get(self, request, *args, **kwargs):
        db_ok = False
        redis_ok = False

        try:
            connections["default"].cursor()
            db_ok = True
        except Exception:
            db_ok = False

        try:
            redis_client = Redis.from_url(getattr(settings, "CELERY_BROKER_URL", getattr(settings, "REDIS_URL", "")))
            redis_ok = bool(redis_client.ping())
        except Exception:
            redis_ok = False

        overall_ok = db_ok and redis_ok
        payload = {
            "status": "ok" if overall_ok else "degraded",
            "checks": {
                "database": "ok" if db_ok else "error",
                "redis": "ok" if redis_ok else "error",
            },
        }
        return Response(payload, status=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE)


class PlatformAdminViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsPlatformAdmin]
    serializer_class = PlatformAnalyticsSerializer
    queryset = AuditLog.objects.none()

    def list(self, request, *args, **kwargs):
        User = apps.get_model("users", "User")
        Mosque = apps.get_model("mosques", "Mosque")
        Donation = apps.get_model("donations", "Donation")
        Complaint = apps.get_model("complaints", "Complaint")
        payload = {
            "users": User.objects.count(),
            "mosques": Mosque.objects.count(),
            "donations": Donation.objects.count(),
            "complaints_by_status": list(
                Complaint.objects.values("status").annotate(total=Count("id")).order_by("status")
            ),
        }
        return Response(payload, status=status.HTTP_200_OK)
