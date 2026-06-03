from apps.projects.models import Project


def get_projects_for_actor(*, actor):
    queryset = Project.objects.select_related("mosque")
    if actor.is_authenticated and actor.is_platform_admin:
        return queryset
    if actor.is_authenticated and actor.is_mosque_admin:
        return queryset.filter(mosque__memberships__user=actor).distinct()
    return queryset.filter(status__in=[Project.Status.APPROVED, Project.Status.ACTIVE], is_blocked=False)
