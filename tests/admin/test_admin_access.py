import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.urls import reverse

from apps.donations.admin import DonationAdmin
from apps.projects.admin import ProjectAdmin
from apps.projects.models import Project
from tests.factories import MosqueFactory, MosqueMembershipFactory, UserFactory


@pytest.mark.django_db
def test_project_admin_limits_mosque_choices_for_mosque_admin(mosque_admin):
    managed_mosque = MosqueFactory()
    other_mosque = MosqueFactory()
    MosqueMembershipFactory(mosque=managed_mosque, user=mosque_admin)

    admin_instance = ProjectAdmin(Project, AdminSite())
    request = RequestFactory().get("/")
    request.user = mosque_admin

    field = Project._meta.get_field("mosque")
    formfield = admin_instance.formfield_for_foreignkey(field, request)

    assert list(formfield.queryset) == [managed_mosque]
    assert other_mosque not in formfield.queryset


@pytest.mark.django_db
def test_mosque_admin_is_denied_from_platform_only_complaints_admin(client, mosque_admin):
    client.force_login(mosque_admin)

    response = client.get(reverse("admin:complaints_complaint_changelist"))

    assert response.status_code in {302, 403}


@pytest.mark.django_db
def test_mosque_admin_donation_queryset_contains_only_managed_mosque_data(mosque_admin):
    managed_mosque = MosqueFactory()
    other_mosque = MosqueFactory()
    MosqueMembershipFactory(mosque=managed_mosque, user=mosque_admin)
    donor = UserFactory()

    from apps.donations.models import Donation

    managed = Donation.objects.create(user=donor, mosque=managed_mosque, amount="100.00", net_amount="95.00")
    Donation.objects.create(user=donor, mosque=other_mosque, amount="200.00", net_amount="190.00")

    admin_instance = DonationAdmin(Donation, AdminSite())
    request = RequestFactory().get("/")
    request.user = mosque_admin

    queryset = admin_instance.get_queryset(request)

    assert list(queryset) == [managed]


@pytest.mark.django_db
def test_admin_index_shows_role_aware_navigation(client, platform_admin, mosque_admin):
    managed_mosque = MosqueFactory()
    MosqueMembershipFactory(mosque=managed_mosque, user=mosque_admin)

    client.force_login(platform_admin)
    platform_response = client.get(reverse("admin:index"))
    assert platform_response.status_code == 200
    assert "Жалобы" in platform_response.content.decode()
    assert "Пользователи" in platform_response.content.decode()

    client.force_login(mosque_admin)
    mosque_response = client.get(reverse("admin:index"))
    assert mosque_response.status_code == 200
    assert "Пожертвования" in mosque_response.content.decode()
    assert "Жалобы" not in mosque_response.content.decode()
    assert "Пользователи" not in mosque_response.content.decode()
