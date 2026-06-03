import pytest

from apps.users.models import User


@pytest.mark.django_db
def test_regular_user_is_not_staff_by_role():
    user = User.objects.create_user(email="user-role@example.com", password="StrongPass123!", full_name="User")

    assert user.is_staff is False


@pytest.mark.django_db
def test_mosque_admin_becomes_staff_by_role():
    user = User.objects.create_user(
        email="mosque-admin@example.com",
        password="StrongPass123!",
        full_name="Mosque Admin",
        role=User.Role.MOSQUE_ADMIN,
    )

    assert user.is_staff is True
