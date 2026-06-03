import pytest
from django.urls import reverse

from tests.factories import MosqueFactory, MosqueMembershipFactory


@pytest.mark.django_db
def test_guest_sees_only_public_mosques(api_client):
    public_mosque = MosqueFactory()
    MosqueFactory(moderation_status="pending")

    response = api_client.get(reverse("mosques-list"))

    assert response.status_code == 200
    ids = [item["id"] for item in response.data["results"]]
    assert public_mosque.id in ids
    assert len(ids) == 1


@pytest.mark.django_db
def test_mosque_admin_can_create_mosque(api_client, mosque_admin):
    api_client.force_authenticate(user=mosque_admin)

    payload = {
        "name": "New Mosque",
        "description": "Desc",
        "city": "Ufa",
        "address": "Street 1",
        "contact_email": "newmosque@example.com",
        "contact_phone": "+79991112233",
    }
    response = api_client.post(reverse("mosques-list"), payload, format="json")

    assert response.status_code == 201
    assert response.data["name"] == "New Mosque"
