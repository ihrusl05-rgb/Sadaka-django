from django.db import models

from common.mixins.models import SoftDeleteModel


class Report(SoftDeleteModel):
    class ScopeType(models.TextChoices):
        PLATFORM = "platform", "Платформа"
        MOSQUE = "mosque", "Мечеть"
        PROJECT = "project", "Проект"

    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        PDF = "pdf", "PDF"

    class Status(models.TextChoices):
        QUEUED = "queued", "В очереди"
        GENERATING = "generating", "Формируется"
        READY = "ready", "Готов"
        FAILED = "failed", "Ошибка"

    requested_by = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="reports", verbose_name="Запросил")
    mosque = models.ForeignKey(
        "mosques.Mosque",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name="Мечеть",
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name="Проект",
    )
    scope_type = models.CharField(max_length=16, choices=ScopeType.choices, verbose_name="Область отчета")
    format = models.CharField(max_length=8, choices=Format.choices, verbose_name="Формат")
    period_start = models.DateField(verbose_name="Период с")
    period_end = models.DateField(verbose_name="Период по")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, verbose_name="Статус")
    file = models.FileField(upload_to="reports/", blank=True, verbose_name="Файл отчета")
    error_message = models.TextField(blank=True, verbose_name="Текст ошибки")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "отчет"
        verbose_name_plural = "отчеты"
