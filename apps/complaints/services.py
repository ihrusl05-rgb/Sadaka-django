from django.utils import timezone

from apps.complaints.models import Complaint
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.platform.services import AuditLogService


class ComplaintService:
    @staticmethod
    def create_complaint(*, actor, **payload) -> Complaint:
        complaint = Complaint.objects.create(user=actor, **payload)
        AuditLogService.log(action="complaint.created", obj=complaint, actor=actor)
        NotificationService.notify_platform_admins(
            title="Новая жалоба",
            message=f"Поступила новая жалоба от пользователя {actor.email}.",
            event=Notification.Event.COMPLAINT_CREATED,
            notification_type=Notification.NotificationType.WARNING,
            link="/admin/complaints/complaint/",
            payload={"complaint_id": complaint.id, "content_type_id": complaint.content_type_id, "object_id": complaint.object_id},
            telegram=True,
        )
        target = complaint.target
        mosque = getattr(target, "mosque", None)
        if mosque is None and hasattr(target, "project"):
            mosque = getattr(target.project, "mosque", None)
        if mosque is not None:
            NotificationService.notify_mosque_admins(
                mosque=mosque,
                title="Поступила жалоба",
                message=f"По объекту мечети «{mosque.name}» поступила новая жалоба.",
                event=Notification.Event.MOSQUE_COMPLAINT_CREATED,
                notification_type=Notification.NotificationType.WARNING,
                link="/profile/",
                payload={"complaint_id": complaint.id, "mosque_id": mosque.id},
            )
        return complaint

    @staticmethod
    def handle_complaint(*, complaint: Complaint, actor, status: str, resolution_note: str) -> Complaint:
        complaint.status = status
        complaint.resolution_note = resolution_note
        complaint.handled_by = actor
        complaint.handled_at = timezone.now()
        complaint.save(update_fields=["status", "resolution_note", "handled_by", "handled_at", "updated_at"])
        AuditLogService.log(action="complaint.handled", obj=complaint, actor=actor, metadata={"status": status})
        NotificationService.notify_user(
            complaint.user,
            title="По вашей жалобе есть ответ",
            message=resolution_note or "Статус вашей жалобы был обновлен.",
            event=Notification.Event.COMPLAINT_REPLY,
            notification_type=Notification.NotificationType.INFO if status == Complaint.Status.IN_REVIEW else Notification.NotificationType.SUCCESS,
            link="/profile/notifications/",
            payload={"complaint_id": complaint.id, "status": status},
            telegram=True,
        )
        return complaint
