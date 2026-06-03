import django_filters

from apps.complaints.models import Complaint


class ComplaintFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter()
    content_type = django_filters.NumberFilter(field_name="content_type_id")

    class Meta:
        model = Complaint
        fields = ["status", "content_type"]
