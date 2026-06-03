from apps.content.models import ContentItem


def get_content_for_actor(*, actor):
    queryset = ContentItem.objects.select_related("mosque")
    if actor.is_authenticated and actor.is_platform_admin:
        return queryset
    if actor.is_authenticated and actor.is_mosque_admin:
        return queryset.filter(mosque__memberships__user=actor).distinct()
    return queryset.filter(moderation_status=ContentItem.ModerationStatus.APPROVED, is_published=True, is_blocked=False)
