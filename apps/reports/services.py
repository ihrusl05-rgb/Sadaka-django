import csv
from io import BytesIO, StringIO

from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from apps.platform.services import AuditLogService
from apps.reports.models import Report


class ReportService:
    @staticmethod
    def request_report(*, actor, **payload) -> Report:
        report = Report.objects.create(requested_by=actor, **payload)
        AuditLogService.log(action="report.requested", obj=report, actor=actor)
        return report

    @staticmethod
    def _build_csv(report: Report) -> bytes:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["report_id", "scope_type", "period_start", "period_end", "status"])
        writer.writerow([report.id, report.scope_type, report.period_start, report.period_end, report.status])
        return output.getvalue().encode("utf-8")

    @staticmethod
    def _build_pdf(report: Report) -> bytes:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.drawString(72, 800, f"Report #{report.id}")
        pdf.drawString(72, 780, f"Scope: {report.scope_type}")
        pdf.drawString(72, 760, f"Period: {report.period_start} - {report.period_end}")
        pdf.save()
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def generate_report(*, report: Report) -> Report:
        report.status = Report.Status.GENERATING
        report.save(update_fields=["status", "updated_at"])
        content = ReportService._build_csv(report) if report.format == Report.Format.CSV else ReportService._build_pdf(report)
        extension = report.format.lower()
        report.file.save(f"report_{report.id}.{extension}", ContentFile(content), save=False)
        report.status = Report.Status.READY
        report.save(update_fields=["file", "status", "updated_at"])
        AuditLogService.log(action="report.generated", obj=report, actor=report.requested_by)
        return report
