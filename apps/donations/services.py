from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.donations.models import Donation
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.platform.services import AuditLogService
from apps.projects.tasks import recompute_project_current_amount_task
from common.services.tasks import dispatch_task


@dataclass
class PaymentResult:
    provider_payment_id: str
    status: str
    metadata: dict


class PaymentService(ABC):
    @abstractmethod
    def create_payment(self, *, donation: Donation) -> PaymentResult: ...

    @abstractmethod
    def confirm_payment(self, *, donation: Donation) -> PaymentResult: ...

    @abstractmethod
    def cancel_payment(self, *, donation: Donation) -> PaymentResult: ...

    @abstractmethod
    def refund_payment(self, *, donation: Donation) -> PaymentResult: ...

    @abstractmethod
    def charge_recurring(self, *, donation: Donation) -> PaymentResult: ...


class MockPaymentService(PaymentService):
    provider_name = "mock"

    def create_payment(self, *, donation: Donation) -> PaymentResult:
        return PaymentResult(provider_payment_id=f"mock_{uuid4().hex}", status=Donation.Status.PROCESSING, metadata={})

    def confirm_payment(self, *, donation: Donation) -> PaymentResult:
        return PaymentResult(provider_payment_id=donation.provider_payment_id, status=Donation.Status.SUCCEEDED, metadata={})

    def cancel_payment(self, *, donation: Donation) -> PaymentResult:
        return PaymentResult(provider_payment_id=donation.provider_payment_id, status=Donation.Status.CANCELLED, metadata={})

    def refund_payment(self, *, donation: Donation) -> PaymentResult:
        return PaymentResult(provider_payment_id=donation.provider_payment_id, status=Donation.Status.REFUNDED, metadata={})

    def charge_recurring(self, *, donation: Donation) -> PaymentResult:
        return PaymentResult(provider_payment_id=f"mock_rec_{uuid4().hex}", status=Donation.Status.SUCCEEDED, metadata={})


class PaymentServiceFactory:
    @staticmethod
    def get(provider: str) -> PaymentService:
        return MockPaymentService()


class DonationService:
    @staticmethod
    def _calculate_amounts(amount: Decimal) -> tuple[Decimal, Decimal]:
        fee = Decimal("0.00")
        net = amount.quantize(Decimal("0.01"))
        return fee, net

    @staticmethod
    def create_donation(*, actor=None, **payload) -> Donation:
        donor_user = payload.pop("user", None)
        guest_full_name = payload.pop("guest_full_name", "").strip()
        guest_email = payload.pop("guest_email", "").strip().lower()
        is_public_anonymous = payload.get("is_public_anonymous", False)

        if getattr(actor, "is_authenticated", False):
            donor_user = donor_user or actor

        if donor_user is None and is_public_anonymous:
            guest_full_name = ""
            guest_email = ""

        if donor_user is None and not is_public_anonymous and not guest_full_name:
            raise ValidationError("Guest donation requires full name.")

        provider_name = payload.pop("provider", "mock")
        fee, net = DonationService._calculate_amounts(payload["amount"])
        try:
            donation = Donation.objects.create(
                user=donor_user,
                platform_fee_amount=fee,
                net_amount=net,
                provider=provider_name,
                guest_full_name=guest_full_name,
                guest_email=guest_email,
                **payload,
            )
            provider = PaymentServiceFactory.get(donation.provider)
            result = provider.create_payment(donation=donation)
            donation.provider_payment_id = result.provider_payment_id
            donation.status = result.status
            donation.metadata = {**donation.metadata, **result.metadata}
            donation.save(update_fields=["provider_payment_id", "status", "metadata", "updated_at"])
            AuditLogService.log(action="donation.created", obj=donation, actor=actor)
            return donation
        except Exception as exc:
            NotificationService.notify_platform_admins(
                title="Ошибка при создании пожертвования",
                message=f"Не удалось создать пожертвование для мечети «{payload['mosque'].name}».",
                event=Notification.Event.PAYMENT_ERROR,
                notification_type=Notification.NotificationType.ERROR,
                link="/admin/donations/donation/",
                payload={"mosque_id": payload["mosque"].id, "error": type(exc).__name__},
                telegram=True,
            )
            raise

    @staticmethod
    def confirm_payment(*, donation: Donation, actor=None) -> Donation:
        provider = PaymentServiceFactory.get(donation.provider)
        result = provider.confirm_payment(donation=donation)
        donation.status = result.status
        donation.paid_at = timezone.now()
        donation.receipt_number = donation.receipt_number or f"RCP-{donation.id:08d}"
        donation.metadata = {**donation.metadata, **result.metadata}
        donation.save(update_fields=["status", "paid_at", "receipt_number", "metadata", "updated_at"])
        if donation.project_id:
            dispatch_task(recompute_project_current_amount_task, donation.project_id)
        AuditLogService.log(action="donation.confirmed", obj=donation, actor=actor)
        if donation.user_id:
            NotificationService.notify_user(
                donation.user,
                title="Пожертвование успешно зачислено",
                message=f"Ваше пожертвование на сумму {donation.amount} ₽ успешно направлено в мечеть «{donation.mosque.name}».",
                event=Notification.Event.DONATION_SUCCESS,
                notification_type=Notification.NotificationType.SUCCESS,
                link=f"/mosques/{donation.mosque.slug}/",
                payload={"donation_id": donation.id, "mosque_id": donation.mosque_id, "project_id": donation.project_id},
                telegram=True,
            )
        NotificationService.notify_mosque_admins(
            mosque=donation.mosque,
            title="Новое пожертвование",
            message=f"Поступило пожертвование {donation.amount} ₽ в пользу мечети «{donation.mosque.name}».",
            event=Notification.Event.MOSQUE_DONATION_RECEIVED,
            notification_type=Notification.NotificationType.SUCCESS,
            link="/profile/",
            payload={"donation_id": donation.id, "project_id": donation.project_id},
        )
        return donation

    @staticmethod
    def cancel_payment(*, donation: Donation, actor=None) -> Donation:
        provider = PaymentServiceFactory.get(donation.provider)
        result = provider.cancel_payment(donation=donation)
        donation.status = result.status
        donation.save(update_fields=["status", "updated_at"])
        AuditLogService.log(action="donation.cancelled", obj=donation, actor=actor)
        return donation

    @staticmethod
    def refund_payment(*, donation: Donation, actor=None) -> Donation:
        provider = PaymentServiceFactory.get(donation.provider)
        result = provider.refund_payment(donation=donation)
        donation.status = result.status
        donation.save(update_fields=["status", "updated_at"])
        if donation.project_id:
            dispatch_task(recompute_project_current_amount_task, donation.project_id)
        AuditLogService.log(action="donation.refunded", obj=donation, actor=actor)
        return donation
