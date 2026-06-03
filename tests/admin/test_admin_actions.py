import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from apps.donations.admin import DonationAdmin, confirm_donations
from apps.donations.models import Donation
from apps.projects.admin import ProjectAdmin, recompute_projects
from apps.projects.models import Project
from tests.factories import MosqueFactory, ProjectFactory, UserFactory


def attach_messages(request):
    setattr(request, "session", {})
    setattr(request, "_messages", FallbackStorage(request))
    return request


@pytest.mark.django_db
def test_project_admin_recompute_action_updates_current_amount(platform_admin):
    mosque = MosqueFactory()
    project = ProjectFactory(mosque=mosque, goal_amount="1000.00", current_amount="0.00")
    donor = UserFactory()
    Donation.objects.create(
        user=donor,
        mosque=mosque,
        project=project,
        amount="100.00",
        net_amount="95.00",
        status=Donation.Status.SUCCEEDED,
    )

    request = attach_messages(RequestFactory().post("/"))
    request.user = platform_admin
    admin_instance = ProjectAdmin(Project, AdminSite())

    recompute_projects(admin_instance, request, Project.objects.filter(pk=project.pk))
    project.refresh_from_db()

    assert str(project.current_amount) == "95.00"


@pytest.mark.django_db
def test_donation_confirm_action_confirms_pending_payment(platform_admin):
    mosque = MosqueFactory()
    donor = UserFactory()
    donation = Donation.objects.create(
        user=donor,
        mosque=mosque,
        amount="100.00",
        net_amount="95.00",
        provider_payment_id="mock_1",
        status=Donation.Status.PENDING,
    )

    request = attach_messages(RequestFactory().post("/"))
    request.user = platform_admin
    admin_instance = DonationAdmin(Donation, AdminSite())

    confirm_donations(admin_instance, request, Donation.objects.filter(pk=donation.pk))
    donation.refresh_from_db()

    assert donation.status == Donation.Status.SUCCEEDED
    assert donation.receipt_number
    assert donation.paid_at is not None
