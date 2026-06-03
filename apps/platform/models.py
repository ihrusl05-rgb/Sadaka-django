from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from common.mixins.models import SoftDeleteModel, TimeStampedModel


class PlatformSettings(TimeStampedModel):
    site_name = models.CharField(max_length=255, default="Sadaka", verbose_name="Название сайта")
    support_email = models.EmailField(verbose_name="Email поддержки")
    default_commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5,
        verbose_name="Комиссия платформы по умолчанию (%)",
    )
    donations_enabled = models.BooleanField(default=True, verbose_name="Пожертвования включены")

    class Meta:
        verbose_name = "настройка платформы"
        verbose_name_plural = "настройки платформы"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.site_name


class AuditLog(TimeStampedModel):
    actor = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        verbose_name="Инициатор",
    )
    action = models.CharField(max_length=128, verbose_name="Действие")
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Тип объекта",
    )
    object_id = models.CharField(max_length=64, blank=True, verbose_name="ID объекта")
    content_object = GenericForeignKey("content_type", "object_id")
    model_label = models.CharField(max_length=128, blank=True, verbose_name="Модель")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Служебные данные")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-адрес")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "запись аудита"
        verbose_name_plural = "журнал аудита"

    def __str__(self):
        return f"{self.action} ({self.model_label}:{self.object_id})"


class MosqueSiteRequest(TimeStampedModel):
    class RequestType(models.TextChoices):
        HELP_FORM = "help_form", "Форма помощи"
        WIDGET_FORM = "widget_form", "Виджет сайта"

    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_PROGRESS = "in_progress", "В работе"
        APPROVED = "approved", "Принята"
        REJECTED = "rejected", "Отклонена"

    request_type = models.CharField(max_length=24, choices=RequestType.choices, verbose_name="Источник заявки")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.NEW, db_index=True, verbose_name="Статус")
    full_name = models.CharField(max_length=255, blank=True, verbose_name="ФИО")
    mosque_name = models.CharField(max_length=255, verbose_name="Название мечети")
    region = models.CharField(max_length=255, blank=True, verbose_name="Регион")
    city = models.CharField(max_length=255, blank=True, verbose_name="Город")
    phone = models.CharField(max_length=32, verbose_name="Телефон")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    source = models.CharField(max_length=64, default="site", verbose_name="Источник")
    reviewed_by_telegram_id = models.BigIntegerField(null=True, blank=True, verbose_name="Telegram ID администратора")
    reviewed_by_username = models.CharField(max_length=255, blank=True, verbose_name="Username администратора")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата обработки")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "заявка на добавление мечети"
        verbose_name_plural = "заявки на добавление мечети"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["request_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.mosque_name} ({self.get_status_display()})"
