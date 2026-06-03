from celery import shared_task

from apps.reports.models import Report
from apps.reports.services import ReportService


@shared_task
def generate_report_task(report_id: int):
    report = Report.objects.get(id=report_id)
    ReportService.generate_report(report=report)
