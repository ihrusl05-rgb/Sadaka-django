from apps.notifications.models import Notification


def get_notifications_for_actor(*, actor):
    if not getattr(actor, "is_authenticated", False):
        return Notification.objects.none()
    queryset = Notification.objects.select_related("user")
    if actor.is_platform_admin:
        return queryset.filter(user=actor) | queryset.filter(user__isnull=True)
    return queryset.filter(user=actor)
