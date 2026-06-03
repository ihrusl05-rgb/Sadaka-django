import django_filters

from apps.notifications.models import Notification


class NotificationFilterSet(django_filters.FilterSet):
    is_read = django_filters.BooleanFilter()
    notification_type = django_filters.CharFilter()
    event = django_filters.CharFilter()

    class Meta:
        model = Notification
        fields = ["is_read", "notification_type", "event"]
