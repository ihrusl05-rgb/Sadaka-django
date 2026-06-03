import pytest
from django.utils import timezone

from apps.support.notifications import SupportNotificationError, send_mosque_widget_request_notification


@pytest.mark.django_db
def test_mosque_widget_notification_uses_configured_telegram_delivery(monkeypatch, settings):
    settings.TELEGRAM_SUPPORT_BOT_TOKEN = "support-bot-token"
    settings.TELEGRAM_ADMIN_CHAT_IDS = (111222333,)

    captured = {}

    def fake_send_telegram_message(**payload):
        captured.update(payload)

    monkeypatch.setattr("apps.support.notifications.send_telegram_message", fake_send_telegram_message)

    send_mosque_widget_request_notification(
        request_snapshot={
            "id": 17,
            "request_type_label": "Виджет сайта",
            "status": "new",
            "status_label": "🆕 Новая",
            "full_name": "Руслан",
            "mosque_name": "Мечеть Ихлас",
            "region": "",
            "city": "Уфа",
            "phone": "+79990000000",
            "comment": "Нужно добавить в каталог",
            "source": "site_widget",
            "created_at": timezone.now(),
            "reviewed_at": None,
            "reviewed_by_username": "",
        }
    )

    assert captured["bot_token"] == "support-bot-token"
    assert captured["chat_ids"] == (111222333,)
    assert "🕌 <b>Заявка на добавление мечети</b>" in captured["text"]
    assert "<b>Заявка:</b> #17" in captured["text"]
    assert "<b>Мечеть:</b> Мечеть Ихлас" in captured["text"]
    assert "<b>Город / регион:</b> Уфа" in captured["text"]
    assert "<b>Телефон:</b> +79990000000" in captured["text"]
    assert captured["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "mosque_request:take:17"


@pytest.mark.django_db
def test_mosque_widget_notification_raises_when_telegram_is_not_configured(settings):
    settings.TELEGRAM_SUPPORT_BOT_TOKEN = ""
    settings.TELEGRAM_ADMIN_CHAT_IDS = ()
    settings.SUPPORT_ADMIN_IDS = ()

    with pytest.raises(SupportNotificationError):
        send_mosque_widget_request_notification(
            request_snapshot={
                "id": 11,
                "request_type_label": "Виджет сайта",
                "status": "new",
                "status_label": "🆕 Новая",
                "full_name": "",
                "mosque_name": "Мечеть Нур",
                "region": "",
                "city": "Казань",
                "phone": "+79990000000",
                "comment": "",
                "source": "site_widget",
                "created_at": timezone.now(),
                "reviewed_at": None,
                "reviewed_by_username": "",
            }
        )
