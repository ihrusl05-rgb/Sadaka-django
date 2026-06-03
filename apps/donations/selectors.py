from apps.donations.models import Donation


def get_donations_for_actor(*, actor):
    queryset = Donation.objects.select_related("user", "mosque", "project", "subscription")
    if not getattr(actor, "is_authenticated", False):
        return Donation.objects.none()
    if actor.is_platform_admin:
        return queryset
    if actor.is_mosque_admin:
        return queryset.filter(mosque__memberships__user=actor).distinct()
    return queryset.filter(user=actor)
