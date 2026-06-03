from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.donations.models import Donation
from apps.subscriptions.models import Subscription
from apps.users.models import TelegramAccount
from apps.users.telegram_auth import TelegramAuthService
from tests.factories import MosqueFactory, TelegramAccountFactory, UserFactory


@pytest.mark.django_db
def test_profile_page_requires_authentication(client):
    response = client.get(reverse("platform:profile"))

    assert response.status_code == 302
    assert reverse("platform:login") in response.url


@pytest.mark.django_db
def test_profile_page_renders_only_current_user_history(client):
    user = UserFactory(full_name="Ахметов Рустам Фаритович", email="rustam@example.com")
    other_user = UserFactory(full_name="Другой Пользователь", email="other@example.com")
    mosque = MosqueFactory(name="Аль-Марджани")

    Donation.objects.create(
        user=user,
        mosque=mosque,
        amount=Decimal("1500.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Donation.Status.SUCCEEDED,
    )
    Donation.objects.create(
        user=other_user,
        mosque=mosque,
        amount=Decimal("900.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Donation.Status.SUCCEEDED,
    )
    Subscription.objects.create(
        user=user,
        mosque=mosque,
        amount=Decimal("700.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Subscription.Status.ACTIVE,
        next_charge_date=date(2026, 6, 1),
    )
    Subscription.objects.create(
        user=other_user,
        mosque=mosque,
        amount=Decimal("300.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Subscription.Status.ACTIVE,
        next_charge_date=date(2026, 6, 1),
    )

    client.force_login(user)
    response = client.get(reverse("platform:profile"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Свежие события" in html
    assert "Рейтинг по приглашениям" in html
    assert "Ваш кабинет сегодня" not in html
    assert "1,500" in html or "1 500" in html
    assert "other@example.com" not in html
    assert "?ref=user-" in html


@pytest.mark.django_db
def test_profile_settings_page_updates_name_parts_without_photo_upload(client):
    user = UserFactory(
        email="phone_79990001122@phone-auth.sadaka.local",
        full_name="Пользователь 1122",
        phone="+79990001122",
        is_phone_verified=True,
    )
    client.force_login(user)

    response = client.post(
        reverse("platform:profile-settings"),
        data={
            "action": "profile",
            "last_name": "Ахметов",
            "first_name": "Рустам",
            "middle_name": "Фаритович",
            "phone": "+79990001122",
            "email": "rustam@example.com",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.last_name == "Ахметов"
    assert user.first_name == "Рустам"
    assert user.middle_name == "Фаритович"
    assert user.full_name == "Ахметов Рустам Фаритович"
    assert user.email == "rustam@example.com"


@pytest.mark.django_db
def test_profile_settings_does_not_change_existing_photo_when_profile_is_updated(client):
    user = UserFactory(email="existing-photo@example.com", full_name="Ахметов Рустам Фаритович")
    user.photo.name = "users/photos/existing-avatar.gif"
    user.save(update_fields=["photo", "updated_at"])
    client.force_login(user)

    response = client.post(
        reverse("platform:profile-settings"),
        data={
            "action": "profile",
            "last_name": "Ахметов",
            "first_name": "Рустам",
            "middle_name": "Фаритович",
            "phone": "",
            "email": "updated@example.com",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.email == "updated@example.com"
    assert user.photo.name == "users/photos/existing-avatar.gif"


@pytest.mark.django_db
def test_profile_page_renders_referral_leaderboard(client):
    leader = UserFactory(full_name="Бф Ватан")
    current_user = UserFactory(full_name="Ахмет Сафин")
    referred_one = UserFactory(full_name="Марат", invited_by=leader)
    referred_two = UserFactory(full_name="Ильяс", invited_by=leader)
    referred_three = UserFactory(full_name="Руслан", invited_by=current_user)
    mosque = MosqueFactory(name="Нур")

    Donation.objects.create(
        user=referred_one,
        mosque=mosque,
        amount=Decimal("1000.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Donation.Status.SUCCEEDED,
    )
    Donation.objects.create(
        user=referred_two,
        mosque=mosque,
        amount=Decimal("500.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Donation.Status.SUCCEEDED,
    )
    Donation.objects.create(
        user=referred_three,
        mosque=mosque,
        amount=Decimal("300.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Donation.Status.SUCCEEDED,
    )

    client.force_login(current_user)
    response = client.get(reverse("platform:profile"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Топ участников по приглашению" in html
    assert "Бф В." in html
    assert "+ 2" in html
    assert "1,500" in html or "1 500" in html


@pytest.mark.django_db
def test_profile_settings_page_renders_forms_and_telegram_status(client):
    user = UserFactory(email="settings@example.com", first_name="Ильдар", phone="+79991112233")
    client.force_login(user)

    response = client.get(reverse("platform:profile-settings"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Настройки" in html
    assert "Личные и контактные данные" in html
    assert "Смена пароля" in html
    assert "Telegram" in html
    assert "Ильдар" in html


@pytest.mark.django_db
def test_profile_settings_allows_setting_password_for_telegram_user_without_existing_password(client):
    user = UserFactory(email="telegram_123@telegram-auth.sadaka.local", first_name="Телеграм")
    user.set_unusable_password()
    user.save(update_fields=["password"])
    client.force_login(user)

    response = client.post(
        reverse("platform:profile-settings"),
        data={
            "action": "password",
            "new_password": "SafePassword123!",
            "new_password_confirm": "SafePassword123!",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.has_usable_password() is True
    assert user.check_password("SafePassword123!")


@pytest.mark.django_db
def test_profile_settings_keeps_telegram_status_after_email_change(client):
    user = UserFactory(
        email="telegram_123456789@telegram-auth.sadaka.local",
        first_name="Ильдар",
    )
    TelegramAccountFactory(user=user, telegram_id=123456789, username="ildar_sadaka")
    client.force_login(user)

    response = client.post(
        reverse("platform:profile-settings"),
        data={
            "action": "profile",
            "last_name": "Ахметов",
            "first_name": "Ильдар",
            "middle_name": "",
            "phone": "",
            "email": "ildar@example.com",
        },
    )

    assert response.status_code == 302
    follow_response = client.get(reverse("platform:profile-settings"))
    html = follow_response.content.decode()
    assert "Telegram привязан" in html
    assert "@ildar_sadaka" in html


@pytest.mark.django_db
def test_profile_telegram_connect_redirects_authenticated_user_to_bot(client, settings):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_test_bot"
    user = UserFactory(email="linked-profile@example.com")
    client.force_login(user)

    response = client.post(reverse("platform:profile-telegram-connect"))

    assert response.status_code == 302
    assert "https://t.me/sadaka_test_bot" in response.url
    assert "login_" in response.url


@pytest.mark.django_db
def test_profile_telegram_connect_rebinds_placeholder_telegram_user_to_current_profile(client):
    user = UserFactory(email="main@example.com", first_name="Основной")
    placeholder_user = UserFactory(email="telegram_123456789@telegram-auth.sadaka.local", first_name="Telegram")
    TelegramAccountFactory(user=placeholder_user, telegram_id=123456789, username="sadaka_user")
    client.force_login(user)

    result = TelegramAuthService.create_login_token(user=user)
    TelegramAuthService.confirm_login_token(
        token=result.login_token.token,
        telegram_id=123456789,
        chat_id=123456789,
        username="sadaka_user",
        first_name="Ильдар",
    )

    user.refresh_from_db()
    telegram_account = TelegramAccount.objects.get(telegram_id=123456789)
    placeholder_user.refresh_from_db()

    assert telegram_account.user_id == user.id
    assert user.telegram_account.telegram_id == 123456789
    assert TelegramAccount.objects.filter(user=placeholder_user).exists() is False
    assert user.first_name == "Основной"


@pytest.mark.django_db
def test_profile_telegram_connect_rebinds_dormant_telegram_only_account_to_current_profile(client):
    user = UserFactory(email="main-2@example.com", first_name="Основной")
    dormant_telegram_user = UserFactory(email="legacy-telegram@example.com", first_name="Legacy")
    dormant_telegram_user.set_unusable_password()
    dormant_telegram_user.save(update_fields=["password"])
    TelegramAccountFactory(user=dormant_telegram_user, telegram_id=2233445566, username="legacy_sadaka")
    client.force_login(user)

    result = TelegramAuthService.create_login_token(user=user)
    TelegramAuthService.confirm_login_token(
        token=result.login_token.token,
        telegram_id=2233445566,
        chat_id=2233445566,
        username="legacy_sadaka",
        first_name="Ильдар",
    )

    user.refresh_from_db()
    telegram_account = TelegramAccount.objects.get(telegram_id=2233445566)

    assert telegram_account.user_id == user.id
    assert user.telegram_account.telegram_id == 2233445566


@pytest.mark.django_db
def test_profile_history_page_renders_separately(client):
    user = UserFactory(full_name="Ахметов Рустам", email="rustam@example.com")
    mosque = MosqueFactory(name="Ихлас")
    Donation.objects.create(
        user=user,
        mosque=mosque,
        amount=Decimal("2100.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Donation.Status.SUCCEEDED,
    )

    client.force_login(user)
    response = client.get(reverse("platform:profile-history"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Все ваши пожертвования" in html
    assert "2,100" in html or "2 100" in html


@pytest.mark.django_db
def test_profile_subscriptions_page_renders_separately(client):
    user = UserFactory(full_name="Ахметов Рустам", email="rustam@example.com")
    mosque = MosqueFactory(name="Ихлас")
    Subscription.objects.create(
        user=user,
        mosque=mosque,
        amount=Decimal("900.00"),
        payment_method=Donation.PaymentMethod.CARD,
        status=Subscription.Status.ACTIVE,
        next_charge_date=date(2026, 6, 1),
    )

    client.force_login(user)
    response = client.get(reverse("platform:profile-subscriptions"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Регулярная помощь" in html
    assert "900" in html
