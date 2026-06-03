from apps.subscriptions.models import Subscription


def get_subscriptions_for_actor(*, actor):
    queryset = Subscription.objects.select_related("user", "mosque", "project")
    if not getattr(actor, "is_authenticated", False):
        return Subscription.objects.none()
    if actor.is_platform_admin:
        return queryset
    if actor.is_mosque_admin:
        return queryset.filter(mosque__memberships__user=actor).distinct()
    return queryset.filter(user=actor)
