import django_filters

from apps.content.models import ContentItem


class ContentFilterSet(django_filters.FilterSet):
    type = django_filters.CharFilter()
    scope = django_filters.CharFilter()
    mosque = django_filters.NumberFilter(field_name="mosque_id")

    class Meta:
        model = ContentItem
        fields = ["type", "scope", "mosque"]
