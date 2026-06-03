import django_filters

from apps.users.models import User


class UserFilterSet(django_filters.FilterSet):
    role = django_filters.CharFilter(field_name="role")
    is_blocked = django_filters.BooleanFilter(field_name="is_blocked")

    class Meta:
        model = User
        fields = ["role", "is_blocked", "is_active"]
