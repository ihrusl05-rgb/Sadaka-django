from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.telegram import format_notification_for_telegram, notify_platform_admin_telegram, notify_user_telegram
from apps.platform.services import AuditLogService

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:
    @staticmethod
    def create_notification(
        *,
        user=None,
        title: str,
        message: str,
        event: str = "",
        notification_type: str = Notification.NotificationType.INFO,
        link: str = "",
        payload: dict | None = None,
        sound_key: str = "default",
        is_sound_enabled: bool = True,
        telegram: bool = False,
    ) -> Notification | None:
        try:
            with transaction.atomic():
                notification = Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    event=event,
                    notification_type=notification_type,
                    link=link,
                    payload=payload or {},
                    sound_key=sound_key,
                    is_sound_enabled=is_sound_enabled,
                )
            AuditLogService.log(action="notification.created", obj=notification, actor=user)
        except Exception:
            logger.exception("Unable to create notification", extra={"event": event, "user_id": getattr(user, "id", None)})
            return None

        if telegram:
            text = format_notification_for_telegram(notification)
            if user is not None:
                notify_user_telegram(user, text)
            else:
                notify_platform_admin_telegram(text)
        return notification

    @staticmethod
    def notify_user(user, **kwargs) -> Notification | None:
        return NotificationService.create_notification(user=user, **kwargs)

    @staticmethod
    def notify_mosque_admins(*, mosque, telegram: bool = False, **kwargs) -> list[Notification]:
        notifications: list[Notification] = []
        admins = User.objects.filter(mosque_memberships__mosque=mosque).distinct()
        for admin in admins:
            notification = NotificationService.create_notification(user=admin, telegram=telegram, **kwargs)
            if notification is not None:
                notifications.append(notification)
        return notifications

    @staticmethod
    def notify_platform_admins(*, telegram: bool = False, **kwargs) -> list[Notification]:
        notifications: list[Notification] = []
        admins = User.objects.filter(is_deleted=False).filter(Q(role=User.Role.PLATFORM_ADMIN) | Q(is_superuser=True)).distinct()
        for admin in admins.distinct():
            notification = NotificationService.create_notification(user=admin, telegram=telegram, **kwargs)
            if notification is not None:
                notifications.append(notification)
        if telegram and not notifications:
            fake_notification = Notification(
                title=kwargs.get("title", ""),
                message=kwargs.get("message", ""),
                event=kwargs.get("event", ""),
                notification_type=kwargs.get("notification_type", Notification.NotificationType.INFO),
                link=kwargs.get("link", ""),
                payload=kwargs.get("payload") or {},
            )
            notify_platform_admin_telegram(format_notification_for_telegram(fake_notification))
        return notifications

    @staticmethod
    def mark_as_read(*, notification: Notification, user) -> Notification:
        if notification.user_id is None and not user.is_platform_admin:
            raise PermissionError("Cannot mark system notification.")
        if notification.user_id and notification.user_id != user.id and not user.is_platform_admin:
            raise PermissionError("Cannot mark чужое уведомление.")
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at", "updated_at"])
            AuditLogService.log(action="notification.read", obj=notification, actor=user)
        return notification

    @staticmethod
    def mark_all_as_read(*, user) -> int:
        queryset = NotificationService.get_user_notifications(user=user).filter(is_read=False)
        count = queryset.count()
        if count:
            now = timezone.now()
            queryset.update(is_read=True, read_at=now, updated_at=now)
            AuditLogService.log(action="notification.read_all", obj=user, actor=user, metadata={"count": count})
        return count

    @staticmethod
    def delete_notification(*, notification: Notification, user) -> None:
        if notification.user_id is None and not user.is_platform_admin:
            raise PermissionError("Cannot delete system notification.")
        if notification.user_id and notification.user_id != user.id and not user.is_platform_admin:
            raise PermissionError("Cannot delete чужое уведомление.")
        notification.soft_delete()
        AuditLogService.log(action="notification.deleted", obj=notification, actor=user)

    @staticmethod
    def get_unread_count(*, user) -> int:
        return NotificationService.get_user_notifications(user=user).filter(is_read=False).count()

    @staticmethod
    def get_user_notifications(*, user):
        queryset = Notification.objects.select_related("user")
        if getattr(user, "is_platform_admin", False):
            return queryset.filter(user=user) | queryset.filter(user__isnull=True)
        return queryset.filter(user=user)
