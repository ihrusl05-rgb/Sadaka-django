import pytest

from apps.users.admin import UserAdminCreationForm
from apps.users.models import User


@pytest.mark.django_db
def test_user_admin_creation_form_hashes_password():
    form = UserAdminCreationForm(
        data={
            "email": "admin-created@example.com",
            "full_name": "Admin Created",
            "phone": "+79990000000",
            "role": User.Role.MOSQUE_ADMIN,
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        }
    )

    assert form.is_valid(), form.errors

    user = form.save()

    assert user.password != "StrongPass123!"
    assert user.check_password("StrongPass123!")
    assert user.is_staff is True
