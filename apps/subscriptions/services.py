from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.donations.services import DonationService, PaymentServiceFactory
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.platform.services import AuditLogService
from apps.subscriptions.models import Subscription


class SubscriptionService:
    @staticmethod
    def create_subscription(*, actor=None, **payload) -> Subscription:
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
            raise ValidationError("Guest subscription requires full name.")

        subscription = Subscription.objects.create(
            user=donor_user,
            guest_full_name=guest_full_name,
            guest_email=guest_email,
            **payload,
        )
        subscription.provider_subscription_id = f"sub_{subscription.id}"
        subscription.save(update_fields=["provider_subscription_id", "updated_at"])
        AuditLogService.log(action="subscription.created", obj=subscription, actor=actor)
        if subscription.user_id:
            NotificationService.notify_user(
                subscription.user,
                title="Ежемесячная поддержка подключена",
                message=f"Подписка на {subscription.amount} ₽ для мечети «{subscription.mosque.name}» успешно создана.",
                event=Notification.Event.RECURRING_PAYMENT_REMINDER,
                notification_type=Notification.NotificationType.INFO,
                link="/profile/",
                payload={"subscription_id": subscription.id},
            )
        return subscription

    @staticmethod
    def update_subscription(*, subscription: Subscription, actor, **payload) -> Subscription:
        for field, value in payload.items():
            setattr(subscription, field, value)
        subscription.save()
        AuditLogService.log(action="subscription.updated", obj=subscription, actor=actor)
        return subscription

    @staticmethod
    def cancel_subscription(*, subscription: Subscription, actor) -> Subscription:
        subscription.status = Subscription.Status.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
        AuditLogService.log(action="subscription.cancelled", obj=subscription, actor=actor)
        return subscription

    @staticmethod
    def process_due_subscription(*, subscription: Subscription) -> Subscription:
        try:
            donation = DonationService.create_donation(
                actor=subscription.user,
                user=subscription.user,
                mosque=subscription.mosque,
                project=subscription.project,
                subscription=subscription,
                amount=subscription.amount,
                payment_method=subscription.payment_method,
                provider=subscription.provider,
                guest_full_name=subscription.guest_full_name,
                guest_email=subscription.guest_email,
                metadata={"subscription_id": subscription.id, "recurring": True},
            )
            DonationService.confirm_payment(donation=donation, actor=subscription.user)
            subscription.last_charged_at = timezone.now()
            subscription.next_charge_date = subscription.next_charge_date + timedelta(days=30)
            subscription.status = Subscription.Status.ACTIVE
            subscription.save(update_fields=["last_charged_at", "next_charge_date", "status", "updated_at"])
            AuditLogService.log(action="subscription.charged", obj=subscription, actor=subscription.user)
            if subscription.user_id:
                NotificationService.notify_user(
                    subscription.user,
                    title="Регулярный платеж выполнен",
                    message=f"Ежемесячная поддержка на сумму {subscription.amount} ₽ для мечети «{subscription.mosque.name}» успешно списана.",
                    event=Notification.Event.RECURRING_PAYMENT_SUCCESS,
                    notification_type=Notification.NotificationType.SUCCESS,
                    link="/profile/",
                    payload={"subscription_id": subscription.id, "donation_id": donation.id},
                    telegram=True,
                )
            return subscription
        except Exception as exc:
            if subscription.user_id:
                NotificationService.notify_user(
                    subscription.user,
                    title="Не удалось выполнить регулярный платеж",
                    message=f"Не удалось списать {subscription.amount} ₽ по подписке для мечети «{subscription.mosque.name}». Попробуйте обновить способ оплаты.",
                    event=Notification.Event.RECURRING_PAYMENT_FAILED,
                    notification_type=Notification.NotificationType.ERROR,
                    link="/profile/",
                    payload={"subscription_id": subscription.id},
                    telegram=True,
                )
            NotificationService.notify_platform_admins(
                title="Ошибка регулярного платежа",
                message=f"Не удалось обработать автоплатеж по подписке #{subscription.id}.",
                event=Notification.Event.PAYMENT_ERROR,
                notification_type=Notification.NotificationType.ERROR,
                link="/admin/subscriptions/subscription/",
                payload={"subscription_id": subscription.id, "error": type(exc).__name__},
                telegram=True,
            )
            raise
