from apps.complaints.models import Complaint


def get_complaints_for_actor(*, actor):
    queryset = Complaint.objects.select_related("user", "handled_by", "content_type")
    if not getattr(actor, "is_authenticated", False):
        return Complaint.objects.none()
    if actor.is_platform_admin:
        return queryset
    return queryset.filter(user=actor)
