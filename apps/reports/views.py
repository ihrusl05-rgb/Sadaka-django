from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.reports.filters import ReportFilterSet
from apps.reports.permissions import ReportAccessPermission
from apps.reports.selectors import get_reports_for_actor
from apps.reports.serializers import ReportSerializer
from apps.reports.services import ReportService
from apps.reports.tasks import generate_report_task
from common.services.tasks import dispatch_task


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [ReportAccessPermission]
    filterset_class = ReportFilterSet
    search_fields = ["requested_by__email"]
    ordering_fields = ["created_at", "period_start", "period_end"]

    def get_queryset(self):
        return get_reports_for_actor(actor=self.request.user)

    def perform_create(self, serializer):
        report = ReportService.request_report(actor=self.request.user, **serializer.validated_data)
        serializer.instance = report
        dispatch_task(generate_report_task, report.id)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        report = self.get_object()
        return Response({"file": report.file.url if report.file else None, "status": report.status})
