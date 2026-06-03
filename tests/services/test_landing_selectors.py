from decimal import Decimal

import pytest
from django.utils import timezone

from apps.donations.models import Donation
from apps.platform.selectors import get_landing_page_context
from tests.factories import MosqueFactory, ProjectFactory, UserFactory


@pytest.mark.django_db
def test_landing_selector_uses_only_successful_donations_and_masks_names():
    now = timezone.now()
    user = UserFactory(full_name="Иван Петров")
    public_mosque = MosqueFactory(name="Кул Шариф", city="Казань")
    smaller_project = ProjectFactory(mosque=public_mosque, title="Ремонт крыши", goal_amount="2000.00")
    featured_project = ProjectFactory(mosque=public_mosque, title="Ремонт забора", goal_amount="1000.00")
    public_mosque.featured_project = featured_project
    public_mosque.save(update_fields=["featured_project"])
    second_mosque = MosqueFactory(name="Ляля-Тюльпан", city="Уфа")
    strongest_project = ProjectFactory(mosque=second_mosque, title="Новый минарет", goal_amount="5000.00")

    Donation.objects.create(
        user=user,
        mosque=public_mosque,
        project=smaller_project,
        amount=Decimal("1500.00"),
        net_amount=Decimal("1500.00"),
        status=Donation.Status.SUCCEEDED,
        payment_method=Donation.PaymentMethod.MOCK,
        provider="mock",
        paid_at=now,
    )
    Donation.objects.create(
        user=None,
        guest_full_name="Марьям Ахметова",
        guest_email="maryam@example.com",
        mosque=public_mosque,
        project=featured_project,
        amount=Decimal("3000.00"),
        net_amount=Decimal("3000.00"),
        status=Donation.Status.SUCCEEDED,
        payment_method=Donation.PaymentMethod.MOCK,
        provider="mock",
        paid_at=now,
    )
    Donation.objects.create(
        user=None,
        guest_full_name="Марьям Ахметова",
        guest_email="maryam@example.com",
        mosque=second_mosque,
        project=strongest_project,
        amount=Decimal("500.00"),
        net_amount=Decimal("500.00"),
        status=Donation.Status.SUCCEEDED,
        payment_method=Donation.PaymentMethod.MOCK,
        provider="mock",
        paid_at=now,
    )
    Donation.objects.create(
        user=user,
        mosque=second_mosque,
        amount=Decimal("10000.00"),
        net_amount=Decimal("10000.00"),
        status=Donation.Status.PENDING,
        payment_method=Donation.PaymentMethod.MOCK,
        provider="mock",
    )

    context = get_landing_page_context()

    assert context["stats"]["total_collected"] == Decimal("5000.00")
    assert context["stats"]["donors_today"] == 2
    assert context["stats"]["donated_today"] == Decimal("5000.00")
    assert context["top_users"]["by_amount"][0]["name"] == "Марьям А."
    assert context["top_users"]["by_amount"][0]["amount"] == Decimal("3500.00")
    assert context["top_users"]["by_count"][0]["count"] == 2
    assert context["top_users"]["by_count"][1]["name"] == "Иван П."
    assert context["available_cities"] == ["Казань", "Уфа"]
    assert context["searchable_mosques"][0]["name"] == "Кул Шариф"
    assert context["searchable_mosques"][0]["city"] == "Казань"
    assert context["searchable_mosques"][0]["collected_total"] == Decimal("4500.00")
    assert context["searchable_mosques"][0]["goal_total"] == Decimal("3000.00")
    assert context["searchable_mosques"][0]["remaining_total"] == Decimal("0.00")
