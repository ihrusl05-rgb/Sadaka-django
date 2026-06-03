from apps.reports.models import Report


def get_reports_for_actor(*, actor):
    queryset = Report.objects.select_related("requested_by", "mosque", "project")
    if not getattr(actor, "is_authenticated", False):
        return Report.objects.none()
    if actor.is_platform_admin:
        return queryset
    if actor.is_mosque_admin:
        return queryset.filter(mosque__memberships__user=actor).distinct()
    return queryset.filter(requested_by=actor)
