import pytest

from apps.users.services import UserService
from tests.factories import UserFactory


@pytest.mark.django_db
def test_update_profile_rebuilds_full_name_from_name_parts():
    user = UserFactory(
        email="phone_79990001122@phone-auth.sadaka.local",
        full_name="Пользователь 1122",
        phone="+79990001122",
        is_phone_verified=True,
    )

    UserService.update_profile(
        user=user,
        last_name="Ахметов",
        first_name="Рустам",
        middle_name="Фаритович",
        email="rustam@example.com",
    )
    user.refresh_from_db()

    assert user.full_name == "Ахметов Рустам Фаритович"
    assert user.email == "rustam@example.com"


@pytest.mark.django_db
def test_update_profile_keeps_placeholder_email_when_blank_value_is_sent():
    user = UserFactory(
        email="phone_79990001122@phone-auth.sadaka.local",
        full_name="Пользователь 1122",
        phone="+79990001122",
        is_phone_verified=True,
    )

    UserService.update_profile(user=user, email="")
    user.refresh_from_db()

    assert user.profile_email == ""
    assert user.email == "phone_79990001122@phone-auth.sadaka.local"


@pytest.mark.django_db
def test_profile_email_hides_telegram_placeholder_email():
    user = UserFactory(
        email="telegram_123456789@telegram-auth.sadaka.local",
        full_name="Telegram User",
    )

    assert user.profile_email == ""
