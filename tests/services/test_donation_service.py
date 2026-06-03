from decimal import Decimal

import pytest

from apps.donations.models import Donation
from apps.donations.services import DonationService
from apps.platform.models import PlatformSettings
from tests.factories import MosqueFactory, ProjectFactory, UserFactory


@pytest.mark.django_db
def test_create_and_confirm_donation_updates_amounts():
    PlatformSettings.objects.get_or_create(pk=1, defaults={"support_email": "support@example.com"})
    user = UserFactory()
    mosque = MosqueFactory(commission_override=Decimal("10.00"))
    project = ProjectFactory(mosque=mosque)

    donation = DonationService.create_donation(
        actor=user,
        mosque=mosque,
        project=project,
        amount=Decimal("100.00"),
        payment_method=Donation.PaymentMethod.MOCK,
        metadata={},
    )

    assert donation.platform_fee_amount == Decimal("0.00")
    assert donation.net_amount == Decimal("100.00")

    donation = DonationService.confirm_payment(donation=donation, actor=user)
    donation.refresh_from_db()

    assert donation.status == Donation.Status.SUCCEEDED
    assert donation.receipt_number.startswith("RCP-")
