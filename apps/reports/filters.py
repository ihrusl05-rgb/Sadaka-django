import django_filters

from apps.reports.models import Report


class ReportFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter()
    scope_type = django_filters.CharFilter()
    format = django_filters.CharFilter()

    class Meta:
        model = Report
        fields = ["status", "scope_type", "format"]
