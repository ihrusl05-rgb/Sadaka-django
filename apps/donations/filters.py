import django_filters

from apps.donations.models import Donation


class DonationFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter()
    mosque = django_filters.NumberFilter(field_name="mosque_id")
    project = django_filters.NumberFilter(field_name="project_id")
    subscription = django_filters.NumberFilter(field_name="subscription_id")

    class Meta:
        model = Donation
        fields = ["status", "mosque", "project", "subscription", "payment_method"]
