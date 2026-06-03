from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.mixins.models import SoftDeleteModel


class Subscription(SoftDeleteModel):
    class Interval(models.TextChoices):
        MONTHLY = "monthly", "Ежемесячно"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        PAUSED = "paused", "Приостановлена"
        CANCELLED = "cancelled", "Отменена"
        PAST_DUE = "past_due", "Просрочена"

    user = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name="Пользователь",
    )
    mosque = models.ForeignKey("mosques.Mosque", on_delete=models.PROTECT, related_name="subscriptions", verbose_name="Мечеть")
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name="Проект",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Сумма")
    currency = models.CharField(max_length=3, default="RUB", verbose_name="Валюта")
    interval = models.CharField(max_length=16, choices=Interval.choices, default=Interval.MONTHLY, verbose_name="Периодичность")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, verbose_name="Статус")
    next_charge_date = models.DateField(default=date.today, verbose_name="Следующее списание")
    last_charged_at = models.DateTimeField(null=True, blank=True, verbose_name="Последнее списание")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата отмены")
    provider_subscription_id = models.CharField(max_length=128, blank=True, verbose_name="ID подписки у провайдера")
    payment_method = models.CharField(max_length=32, default="mock", verbose_name="Способ оплаты")
    provider = models.CharField(max_length=32, default="mock", verbose_name="Платежный провайдер")
    guest_full_name = models.CharField(max_length=255, blank=True, verbose_name="Имя гостя")
    guest_email = models.EmailField(blank=True, verbose_name="Email гостя")
    is_public_anonymous = models.BooleanField(default=False, verbose_name="Показывать анонимно")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Служебные данные")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "mosque", "amount"],
                condition=Q(status="active", project__isnull=True),
                name="unique_active_subscription_per_mosque_amount",
            ),
            models.UniqueConstraint(
                fields=["user", "project", "amount"],
                condition=Q(status="active", project__isnull=False),
                name="unique_active_subscription_per_project_amount",
            )
        ]
        ordering = ["-created_at"]
        verbose_name = "подписка"
        verbose_name_plural = "подписки"

    def __str__(self):
        return f"{self.donor_email} -> {self.mosque.name}"

    @property
    def donor_name(self) -> str:
        if self.user_id and self.user.full_name:
            return self.user.full_name
        if self.guest_full_name:
            return self.guest_full_name
        if self.user_id and self.user.email:
            return self.user.email
        if self.guest_email:
            return self.guest_email
        return "Аноним"

    @property
    def donor_email(self) -> str:
        if self.user_id and self.user.email:
            return self.user.email
        if self.guest_email:
            return self.guest_email
        return "anonymous@sadaka.local"

    def clean(self):
        if self.project_id and self.project.mosque_id != self.mosque_id:
            raise ValidationError("Project must belong to the selected mosque.")
