from celery import shared_task

from apps.donations.models import Donation
from apps.donations.services import DonationService


@shared_task
def confirm_donation_payment_task(donation_id: int):
    donation = Donation.objects.get(id=donation_id)
    DonationService.confirm_payment(donation=donation)
