import pytest
from django.urls import reverse

from apps.users.max_auth import MaxAuthService
from apps.users.models import MaxAuthCode, TelegramAuthCode, User
from apps.users.telegram_auth import TelegramAuthService


def _disable_telegram_send(monkeypatch):
    def _stub_send(*, account, code):
        return None

    monkeypatch.setattr(TelegramAuthService, "_send_code_via_bot", staticmethod(_stub_send))


def _disable_max_send(monkeypatch):
    def _stub_send(*, account, code):
        return None

    monkeypatch.setattr(MaxAuthService, "_send_code_via_bot", staticmethod(_stub_send))


@pytest.mark.django_db
def test_register_returns_created_user(api_client):
    url = reverse("auth-register")
    payload = {
        "email": "new@example.com",
        "full_name": "New User",
        "phone": "+79990001122",
        "password": "StrongPass123!",
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == 201
    assert response.data["email"] == payload["email"]


@pytest.mark.django_db
def test_login_returns_tokens(api_client, user):
    url = reverse("auth-login")

    response = api_client.post(url, {"email": user.email, "password": "StrongPass123!"}, format="json")

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_telegram_login_token_returns_deep_link(api_client, settings):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_auth_bot"
    url = reverse("auth-telegram-login-token")

    response = api_client.post(url, {}, format="json")

    assert response.status_code == 201
    assert response.data["token"]
    assert response.data["telegram_url"] == f"https://t.me/sadaka_auth_bot?start=login_{response.data['token']}"


@pytest.mark.django_db
def test_telegram_request_and_verify_code_returns_tokens(api_client, settings, monkeypatch):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_auth_bot"
    _disable_telegram_send(monkeypatch)

    login_token_response = api_client.post(reverse("auth-telegram-login-token"), {}, format="json")
    token = login_token_response.data["token"]

    TelegramAuthService.confirm_login_token(
        token=token,
        telegram_id=123456789,
        chat_id=123456789,
        username="sadaka_user",
        first_name="Ильдар",
    )

    status_response = api_client.get(reverse("auth-telegram-login-status", kwargs={"token": token}))
    assert status_response.status_code == 200
    assert status_response.data["status"] == "confirmed"
    assert status_response.data["display_name"] == "@sadaka_user"

    code_response = api_client.post(reverse("auth-telegram-request-code"), {"token": token}, format="json")
    assert code_response.status_code == 201
    assert code_response.data["ok"] is True
    assert len(code_response.data["debug_code"]) == 6

    verify_response = api_client.post(
        reverse("auth-telegram-verify-code"),
        {"token": token, "code": code_response.data["debug_code"]},
        format="json",
    )

    assert verify_response.status_code == 200
    assert verify_response.data["ok"] is True
    assert verify_response.data["user"]["telegram_id"] == 123456789
    assert verify_response.data["user"]["telegram_username"] == "sadaka_user"
    assert verify_response.data["user"]["full_name"] == "Ильдар"
    assert "access" in verify_response.data["tokens"]
    assert "refresh" in verify_response.data["tokens"]
    assert User.objects.filter(telegram_account__telegram_id=123456789).exists()


@pytest.mark.django_db
def test_telegram_verify_code_enforces_attempt_limit(api_client, settings, monkeypatch):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_auth_bot"
    _disable_telegram_send(monkeypatch)

    login_token_response = api_client.post(reverse("auth-telegram-login-token"), {}, format="json")
    token = login_token_response.data["token"]
    TelegramAuthService.confirm_login_token(
        token=token,
        telegram_id=987654321,
        chat_id=987654321,
        username="test_user",
    )
    api_client.post(reverse("auth-telegram-request-code"), {"token": token}, format="json")

    for attempt in range(TelegramAuthService.MAX_ATTEMPTS):
        response = api_client.post(
            reverse("auth-telegram-verify-code"),
            {"token": token, "code": "000000"},
            format="json",
        )
        assert response.status_code == 400
        if attempt < TelegramAuthService.MAX_ATTEMPTS - 1:
            assert "Код неверный. Осталось" in str(response.data)

    final_response = api_client.post(
        reverse("auth-telegram-verify-code"),
        {"token": token, "code": "000000"},
        format="json",
    )

    assert final_response.status_code == 400
    assert "Код заблокирован" in str(final_response.data)
    assert TelegramAuthCode.objects.filter(login_token__token=token, telegram_id=987654321).exists()


@pytest.mark.django_db
def test_telegram_request_code_invalidates_previous_code(api_client, settings, monkeypatch):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_auth_bot"
    _disable_telegram_send(monkeypatch)

    login_token_response = api_client.post(reverse("auth-telegram-login-token"), {}, format="json")
    token = login_token_response.data["token"]
    TelegramAuthService.confirm_login_token(
        token=token,
        telegram_id=555666777,
        chat_id=555666777,
        username="madina",
    )

    first_code = api_client.post(reverse("auth-telegram-request-code"), {"token": token}, format="json").data["debug_code"]
    second_code = api_client.post(reverse("auth-telegram-request-code"), {"token": token}, format="json").data["debug_code"]

    assert first_code != second_code

    stale_response = api_client.post(
        reverse("auth-telegram-verify-code"),
        {"token": token, "code": first_code},
        format="json",
    )
    assert stale_response.status_code == 400
    assert "Код неверный" in str(stale_response.data)

    fresh_response = api_client.post(
        reverse("auth-telegram-verify-code"),
        {"token": token, "code": second_code},
        format="json",
    )
    assert fresh_response.status_code == 200
    assert fresh_response.data["ok"] is True


@pytest.mark.django_db
def test_telegram_verify_code_cannot_be_reused(api_client, settings, monkeypatch):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_auth_bot"
    _disable_telegram_send(monkeypatch)

    login_token_response = api_client.post(reverse("auth-telegram-login-token"), {}, format="json")
    token = login_token_response.data["token"]
    TelegramAuthService.confirm_login_token(
        token=token,
        telegram_id=222333444,
        chat_id=222333444,
        username="ibrahim",
    )
    code = api_client.post(reverse("auth-telegram-request-code"), {"token": token}, format="json").data["debug_code"]

    first_response = api_client.post(
        reverse("auth-telegram-verify-code"),
        {"token": token, "code": code},
        format="json",
    )
    assert first_response.status_code == 200

    second_response = api_client.post(
        reverse("auth-telegram-verify-code"),
        {"token": token, "code": code},
        format="json",
    )
    assert second_response.status_code == 400
    assert "Вход уже подтвержден" in str(second_response.data)


@pytest.mark.django_db
def test_telegram_confirm_accepts_only_auth_bot_token(api_client, settings, monkeypatch):
    settings.TELEGRAM_AUTH_BOT_TOKEN = "auth-token"
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_auth_bot"
    _disable_telegram_send(monkeypatch)

    login_token_response = api_client.post(reverse("auth-telegram-login-token"), {}, format="json")
    token = login_token_response.data["token"]
    payload = {
        "token": token,
        "telegram_id": 123456789,
        "chat_id": 123456789,
        "username": "sadaka_user",
        "first_name": "Ильдар",
        "last_name": "",
    }

    forbidden_response = api_client.post(
        reverse("auth-telegram-confirm"),
        payload,
        format="json",
        HTTP_X_TELEGRAM_BOT_TOKEN="wrong-token",
    )
    assert forbidden_response.status_code == 403

    allowed_response = api_client.post(
        reverse("auth-telegram-confirm"),
        payload,
        format="json",
        HTTP_X_TELEGRAM_BOT_TOKEN="auth-token",
    )
    assert allowed_response.status_code == 200
    assert allowed_response.data["ok"] is True


@pytest.mark.django_db
def test_max_login_token_returns_deep_link(api_client, settings):
    settings.MAX_AUTH_BOT_USERNAME = "id025404324718_5_bot"

    response = api_client.post(reverse("auth-max-login-token"), {}, format="json")

    assert response.status_code == 201
    assert response.data["token"]
    assert response.data["max_url"] == f"https://max.ru/id025404324718_5_bot?start=login_{response.data['token']}"


@pytest.mark.django_db
def test_max_request_and_verify_code_returns_tokens(api_client, settings, monkeypatch):
    settings.MAX_AUTH_BOT_USERNAME = "id025404324718_5_bot"
    _disable_max_send(monkeypatch)

    login_token_response = api_client.post(reverse("auth-max-login-token"), {}, format="json")
    token = login_token_response.data["token"]

    MaxAuthService.confirm_login_token(
        token=token,
        max_user_id=123456789,
        chat_id=123456789,
        username="sadaka_max",
        first_name="Макс",
    )

    status_response = api_client.get(reverse("auth-max-login-status", kwargs={"token": token}))
    assert status_response.status_code == 200
    assert status_response.data["status"] == "confirmed"
    assert status_response.data["display_name"] == "@sadaka_max"

    code_response = api_client.post(reverse("auth-max-request-code"), {"token": token}, format="json")
    assert code_response.status_code == 201
    assert code_response.data["ok"] is True
    assert len(code_response.data["debug_code"]) == 6

    verify_response = api_client.post(
        reverse("auth-max-verify-code"),
        {"token": token, "code": code_response.data["debug_code"]},
        format="json",
    )

    assert verify_response.status_code == 200
    assert verify_response.data["ok"] is True
    assert verify_response.data["user"]["max_user_id"] == 123456789
    assert verify_response.data["user"]["max_username"] == "sadaka_max"
    assert verify_response.data["user"]["full_name"] == "Макс"
    assert "access" in verify_response.data["tokens"]
    assert "refresh" in verify_response.data["tokens"]
    assert User.objects.filter(max_account__max_user_id=123456789).exists()


@pytest.mark.django_db
def test_max_webhook_confirms_login_and_issues_code(api_client, settings, monkeypatch):
    settings.MAX_AUTH_BOT_USERNAME = "id025404324718_5_bot"
    settings.MAX_AUTH_WEBHOOK_SECRET = "webhook-secret"
    _disable_max_send(monkeypatch)

    login_token_response = api_client.post(reverse("auth-max-login-token"), {}, format="json")
    token = login_token_response.data["token"]

    response = api_client.post(
        reverse("max-webhook"),
        {
            "update_type": "bot_started",
            "payload": f"login_{token}",
            "user": {
                "user_id": 888777666,
                "username": "max_web_user",
                "first_name": "Амир",
            },
            "chat": {
                "chat_id": 888777666,
            },
        },
        format="json",
        HTTP_X_MAX_BOT_API_SECRET="webhook-secret",
    )

    assert response.status_code == 200
    status_response = api_client.get(reverse("auth-max-login-status", kwargs={"token": token}))
    assert status_response.status_code == 200
    assert status_response.data["status"] == "confirmed"
    assert len(status_response.data["debug_code"]) == 6
    assert MaxAuthCode.objects.filter(login_token__token=token, max_user_id=888777666).exists()
