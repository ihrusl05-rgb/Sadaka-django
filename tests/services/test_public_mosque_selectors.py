from decimal import Decimal

import pytest

from apps.donations.models import Donation
from apps.platform.selectors import get_public_mosque_detail_context
from apps.subscriptions.models import Subscription
from tests.factories import MosqueFactory, ProjectFactory


@pytest.mark.django_db
def test_public_mosque_detail_selector_builds_support_sections_and_respects_anonymity():
    mosque = MosqueFactory(legal_name="Юр. лицо", inn="1234567890")
    featured_project = ProjectFactory(mosque=mosque, title="Ремонт крыши", goal_amount="5000.00", description="Текущий проект")
    ProjectFactory(mosque=mosque, title="Ремонт забора", goal_amount="2000.00", description="Второй проект")
    ProjectFactory(mosque=mosque, title="Архивный сбор", goal_amount="1000.00", current_amount="1000.00", status="completed")
    mosque.featured_project = featured_project
    mosque.save(update_fields=["featured_project"])

    Donation.objects.create(
        mosque=mosque,
        amount=Decimal("1000.00"),
        status=Donation.Status.SUCCEEDED,
        payment_method=Donation.PaymentMethod.CARD,
        guest_full_name="Открытый Донор",
        guest_email="open@example.com",
    )
    recurring_subscription = Subscription.objects.create(
        mosque=mosque,
        amount=Decimal("700.00"),
        payment_method=Donation.PaymentMethod.SBP,
        guest_full_name="Скрытый Подписчик",
        guest_email="hidden@example.com",
        status=Subscription.Status.ACTIVE,
        is_public_anonymous=True,
    )
    Donation.objects.create(
        mosque=mosque,
        subscription=recurring_subscription,
        amount=Decimal("700.00"),
        status=Donation.Status.SUCCEEDED,
        payment_method=Donation.PaymentMethod.SBP,
        guest_full_name="Скрытый Подписчик",
        guest_email="hidden@example.com",
        is_public_anonymous=True,
        metadata={"recurring": True},
    )

    context = get_public_mosque_detail_context(mosque=mosque)

    assert context["collected_total"] == Decimal("1700.00")
    assert context["goal_total"] == Decimal("7000.00")
    assert context["featured_project"].title == "Ремонт крыши"
    assert len(context["active_projects"]) == 2
    assert context["active_projects"][0]["is_featured"] is True
    assert context["completed_projects"][0]["title"] == "Архивный сбор"
    assert context["recent_supporters"][0]["name"] == "Анонимный спонсор"
    assert context["top_autopayments"][0]["name"] == "Анонимный спонсор"
    assert context["ummah_members"][0]["name"] == "Аноним"
    assert context["legal_info"] == [("Наименование", "Юр. лицо"), ("ИНН", "1234567890")]


@pytest.mark.django_db
def test_public_mosque_detail_selector_uses_fallback_goal_when_no_active_project():
    mosque = MosqueFactory()

    context = get_public_mosque_detail_context(mosque=mosque)

    assert context["goal_total"] == Decimal("1.00")
    assert context["progress_percent"] == 0
