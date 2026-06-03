from celery import shared_task

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService


@shared_task
def send_notification_task(
    user_id: int,
    title: str,
    message: str,
    event: str = "",
    notification_type: str = Notification.NotificationType.INFO,
    link: str = "",
    payload: dict | None = None,
):
    User = Notification._meta.apps.get_model("users", "User")
    user = User.objects.get(id=user_id)
    NotificationService.create_notification(
        user=user,
        title=title,
        message=message,
        event=event,
        notification_type=notification_type,
        link=link,
        payload=payload,
    )
