import django_filters

from apps.mosques.models import Mosque


class MosqueFilterSet(django_filters.FilterSet):
    city = django_filters.CharFilter(lookup_expr="icontains")
    moderation_status = django_filters.CharFilter()
    verification_status = django_filters.CharFilter()
    is_blocked = django_filters.BooleanFilter()

    class Meta:
        model = Mosque
        fields = ["city", "moderation_status", "verification_status", "is_blocked"]
