import django_filters

from apps.subscriptions.models import Subscription


class SubscriptionFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter()
    mosque = django_filters.NumberFilter(field_name="mosque_id")
    project = django_filters.NumberFilter(field_name="project_id")

    class Meta:
        model = Subscription
        fields = ["status", "mosque", "project", "interval"]
