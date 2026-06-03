from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from common.mixins.models import SoftDeleteModel


class Complaint(SoftDeleteModel):
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_REVIEW = "in_review", "На рассмотрении"
        RESOLVED = "resolved", "Решена"
        REJECTED = "rejected", "Отклонена"

    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="complaints", verbose_name="Подал жалобу")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="Тип объекта")
    object_id = models.PositiveBigIntegerField(verbose_name="ID объекта")
    target = GenericForeignKey("content_type", "object_id")
    description = models.TextField(verbose_name="Описание жалобы")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW, verbose_name="Статус")
    resolution_note = models.TextField(blank=True, verbose_name="Комментарий по решению")
    handled_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handled_complaints",
        verbose_name="Обработал",
    )
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата обработки")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "жалоба"
        verbose_name_plural = "жалобы"
