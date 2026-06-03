import uuid

from django.core.exceptions import ValidationError
from django.db import models

from common.mixins.models import SoftDeleteModel


class Donation(SoftDeleteModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает оплаты"
        PROCESSING = "processing", "В обработке"
        SUCCEEDED = "succeeded", "Оплачено"
        FAILED = "failed", "Ошибка оплаты"
        REFUNDED = "refunded", "Возвращено"
        CANCELLED = "cancelled", "Отменено"

    class PaymentMethod(models.TextChoices):
        CARD = "card", "Банковская карта"
        SBP = "sbp", "SBP"
        MOCK = "mock", "Тестовый платеж"

    user = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="donations",
        verbose_name="Жертвователь",
    )
    mosque = models.ForeignKey("mosques.Mosque", on_delete=models.PROTECT, related_name="donations", verbose_name="Мечеть")
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="donations",
        verbose_name="Проект",
    )
    subscription = models.ForeignKey(
        "subscriptions.Subscription",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="donations",
        verbose_name="Подписка",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Сумма пожертвования")
    currency = models.CharField(max_length=3, default="RUB", verbose_name="Валюта")
    platform_fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Комиссия платформы",
    )
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма к зачислению")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, verbose_name="Статус оплаты")
    payment_method = models.CharField(
        max_length=32,
        choices=PaymentMethod.choices,
        default=PaymentMethod.MOCK,
        verbose_name="Способ оплаты",
    )
    provider = models.CharField(max_length=32, default="mock", verbose_name="Платежный провайдер")
    provider_payment_id = models.CharField(max_length=128, blank=True, verbose_name="ID платежа у провайдера")
    receipt_number = models.CharField(max_length=64, blank=True, verbose_name="Номер квитанции")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата оплаты")
    guest_full_name = models.CharField(max_length=255, blank=True, verbose_name="Имя гостя")
    guest_email = models.EmailField(blank=True, verbose_name="Email гостя")
    is_public_anonymous = models.BooleanField(default=False, verbose_name="Показывать анонимно")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Служебные данные")
    external_reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Внешний идентификатор")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "пожертвование"
        verbose_name_plural = "пожертвования"

    def __str__(self):
        return f"{self.donor_email}: {self.amount} {self.currency}"

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
