from decimal import Decimal

import pytest

from apps.donations.models import Donation
from apps.donations.services import DonationService
from apps.subscriptions.models import Subscription
from apps.subscriptions.services import SubscriptionService
from tests.factories import MosqueFactory


@pytest.mark.django_db
def test_guest_donation_can_be_created_and_confirmed():
    mosque = MosqueFactory()

    donation = DonationService.create_donation(
        actor=None,
        mosque=mosque,
        amount=Decimal("1200.00"),
        payment_method=Donation.PaymentMethod.MOCK,
        guest_full_name="Гость Тестов",
        guest_email="guest@example.com",
        metadata={"public_checkout": True},
    )
    donation = DonationService.confirm_payment(donation=donation, actor=None)

    assert donation.user is None
    assert donation.guest_full_name == "Гость Тестов"
    assert donation.guest_email == "guest@example.com"
    assert donation.status == Donation.Status.SUCCEEDED


@pytest.mark.django_db
def test_guest_donation_without_email_is_allowed():
    mosque = MosqueFactory()

    donation = DonationService.create_donation(
        actor=None,
        mosque=mosque,
        amount=Decimal("1200.00"),
        payment_method=Donation.PaymentMethod.MOCK,
        guest_full_name="Гость Тестов",
        guest_email="",
        metadata={"public_checkout": True},
    )

    assert donation.guest_email == ""


@pytest.mark.django_db
def test_guest_subscription_due_charge_creates_guest_donation():
    mosque = MosqueFactory()
    subscription = SubscriptionService.create_subscription(
        actor=None,
        mosque=mosque,
        amount=Decimal("900.00"),
        interval=Subscription.Interval.MONTHLY,
        payment_method=Donation.PaymentMethod.MOCK,
        guest_full_name="Садака Гость",
        guest_email="monthly@example.com",
        metadata={"public_checkout": True},
    )

    charged_subscription = SubscriptionService.process_due_subscription(subscription=subscription)
    donation = Donation.objects.get(subscription=subscription)

    assert charged_subscription.user is None
    assert charged_subscription.guest_email == "monthly@example.com"
    assert donation.user is None
    assert donation.guest_email == "monthly@example.com"
    assert donation.status == Donation.Status.SUCCEEDED


@pytest.mark.django_db
def test_guest_subscription_without_email_is_allowed():
    mosque = MosqueFactory()

    subscription = SubscriptionService.create_subscription(
        actor=None,
        mosque=mosque,
        amount=Decimal("900.00"),
        interval=Subscription.Interval.MONTHLY,
        payment_method=Donation.PaymentMethod.MOCK,
        guest_full_name="Садака Гость",
        guest_email="",
        metadata={"public_checkout": True},
    )

    assert subscription.guest_email == ""
