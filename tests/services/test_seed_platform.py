import pytest
from django.core.management import call_command

from apps.users.models import User


@pytest.mark.django_db
def test_seed_platform_resets_known_demo_passwords():
    user = User.objects.create_user(
        email="imam@sadaka.local",
        password="WrongPass123!",
        full_name="Mosque Admin",
        role=User.Role.MOSQUE_ADMIN,
    )
    user.password = "imam1234"
    user.save(update_fields=["password"])

    call_command("seed_platform")

    user.refresh_from_db()

    assert user.check_password("imam12345")
