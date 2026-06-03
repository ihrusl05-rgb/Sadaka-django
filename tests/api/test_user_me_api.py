import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from tests.factories import UserFactory

GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


@pytest.mark.django_db
def test_users_me_hides_phone_auth_placeholder_email(api_client):
    user = UserFactory(
        email="phone_79990001122@phone-auth.sadaka.local",
        full_name="Пользователь 1122",
        phone="+79990001122",
        is_phone_verified=True,
    )
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("users-me"))

    assert response.status_code == 200
    assert response.data["email"] == ""


@pytest.mark.django_db
def test_users_me_patch_updates_profile_with_multipart(api_client, settings):
    settings.MEDIA_ROOT = settings.BASE_DIR / "test-media"
    user = UserFactory(
        email="phone_79990001122@phone-auth.sadaka.local",
        full_name="Пользователь 1122",
        phone="+79990001122",
        is_phone_verified=True,
    )
    api_client.force_authenticate(user=user)

    response = api_client.patch(
        reverse("users-me"),
        {
            "last_name": "Ахметов",
            "first_name": "Рустам",
            "middle_name": "Фаритович",
            "email": "rustam@example.com",
            "photo": SimpleUploadedFile("avatar.gif", GIF_BYTES, content_type="image/gif"),
        },
        format="multipart",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.full_name == "Ахметов Рустам Фаритович"
    assert user.email == "rustam@example.com"
    assert user.photo.name.startswith("users/photos/avatar")
    assert user.photo.name.endswith(".gif")
    assert response.data["email"] == "rustam@example.com"
