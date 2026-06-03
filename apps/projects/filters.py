import django_filters

from apps.projects.models import Project


class ProjectFilterSet(django_filters.FilterSet):
    mosque = django_filters.NumberFilter(field_name="mosque_id")
    status = django_filters.CharFilter()
    is_blocked = django_filters.BooleanFilter()

    class Meta:
        model = Project
        fields = ["mosque", "status", "is_blocked"]
