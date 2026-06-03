from apps.mosques.models import Mosque


def get_public_mosque_queryset():
    return Mosque.objects.filter(
        moderation_status=Mosque.ModerationStatus.APPROVED,
        verification_status=Mosque.VerificationStatus.VERIFIED,
        is_blocked=False,
    )


def get_mosques_for_actor(*, actor):
    queryset = Mosque.objects.all().prefetch_related("memberships__user")
    if actor.is_authenticated and actor.is_platform_admin:
        return queryset
    if actor.is_authenticated and actor.is_mosque_admin:
        return queryset.filter(memberships__user=actor).distinct()
    return get_public_mosque_queryset()
