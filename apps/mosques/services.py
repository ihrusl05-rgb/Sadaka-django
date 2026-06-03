from django.utils import timezone

from apps.mosques.models import Mosque, MosqueMembership
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.platform.services import AuditLogService


class MosqueService:
    @staticmethod
    def create_mosque(*, actor, **payload) -> Mosque:
        mosque = Mosque(created_by=actor, **payload)
        mosque.full_clean(exclude=["slug"])
        mosque.save()
        MosqueMembership.objects.get_or_create(mosque=mosque, user=actor, defaults={"is_primary": True})
        AuditLogService.log(action="mosque.created", obj=mosque, actor=actor)
        NotificationService.notify_platform_admins(
            title="Мечеть отправлена на модерацию",
            message=f"Мечеть «{mosque.name}» создана и ожидает проверки.",
            event=Notification.Event.MOSQUE_SUBMITTED,
            notification_type=Notification.NotificationType.INFO,
            link="/admin/mosques/mosque/",
            payload={"mosque_id": mosque.id, "created_by_id": actor.id if actor else None},
            telegram=True,
        )
        return mosque

    @staticmethod
    def update_mosque(*, mosque: Mosque, actor, **payload) -> Mosque:
        for field, value in payload.items():
            setattr(mosque, field, value)
        mosque.full_clean()
        mosque.save()
        AuditLogService.log(action="mosque.updated", obj=mosque, actor=actor)
        return mosque

    @staticmethod
    def approve(*, mosque: Mosque, actor) -> Mosque:
        mosque.moderation_status = Mosque.ModerationStatus.APPROVED
        mosque.published_at = mosque.published_at or timezone.now()
        mosque.save(update_fields=["moderation_status", "published_at", "updated_at"])
        AuditLogService.log(action="mosque.approved", obj=mosque, actor=actor)
        if mosque.created_by_id:
            NotificationService.notify_user(
                mosque.created_by,
                title="Мечеть одобрена",
                message=f"Мечеть «{mosque.name}» прошла модерацию и опубликована на платформе.",
                event=Notification.Event.MOSQUE_APPROVED,
                notification_type=Notification.NotificationType.SUCCESS,
                link=f"/mosques/{mosque.slug}/",
                payload={"mosque_id": mosque.id},
                telegram=True,
            )
        NotificationService.notify_mosque_admins(
            mosque=mosque,
            title="Мечеть опубликована",
            message=f"Мечеть «{mosque.name}» одобрена и доступна на платформе.",
            event=Notification.Event.MOSQUE_APPROVED,
            notification_type=Notification.NotificationType.SUCCESS,
            link=f"/mosques/{mosque.slug}/",
            payload={"mosque_id": mosque.id},
        )
        return mosque

    @staticmethod
    def reject(*, mosque: Mosque, actor) -> Mosque:
        mosque.moderation_status = Mosque.ModerationStatus.REJECTED
        mosque.save(update_fields=["moderation_status", "updated_at"])
        AuditLogService.log(action="mosque.rejected", obj=mosque, actor=actor)
        if mosque.created_by_id:
            NotificationService.notify_user(
                mosque.created_by,
                title="Мечеть отклонена",
                message=f"Мечеть «{mosque.name}» пока не прошла модерацию. Проверьте данные и отправьте заявку повторно.",
                event=Notification.Event.MOSQUE_REJECTED,
                notification_type=Notification.NotificationType.WARNING,
                link="/profile/",
                payload={"mosque_id": mosque.id},
                telegram=True,
            )
        return mosque

    @staticmethod
    def verify(*, mosque: Mosque, actor) -> Mosque:
        mosque.verification_status = Mosque.VerificationStatus.VERIFIED
        mosque.save(update_fields=["verification_status", "updated_at"])
        AuditLogService.log(action="mosque.verified", obj=mosque, actor=actor)
        return mosque

    @staticmethod
    def block(*, mosque: Mosque, actor, reason: str = "") -> Mosque:
        mosque.is_blocked = True
        mosque.blocked_at = timezone.now()
        mosque.blocked_reason = reason
        mosque.save(update_fields=["is_blocked", "blocked_at", "blocked_reason", "updated_at"])
        AuditLogService.log(action="mosque.blocked", obj=mosque, actor=actor, metadata={"reason": reason})
        return mosque

    @staticmethod
    def unblock(*, mosque: Mosque, actor) -> Mosque:
        mosque.is_blocked = False
        mosque.blocked_reason = ""
        mosque.save(update_fields=["is_blocked", "blocked_reason", "updated_at"])
        AuditLogService.log(action="mosque.unblocked", obj=mosque, actor=actor)
        return mosque
