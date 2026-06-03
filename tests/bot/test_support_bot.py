import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot.support_bot import (
    ADMIN_UNAVAILABLE_TEXT,
    _build_main_menu,
    _build_ticket_list_keyboard,
    _build_ticket_overview_keyboard,
    admin_handler,
)


def test_support_bot_main_menu_has_expected_sections():
    keyboard = _build_main_menu().inline_keyboard
    labels = [button.text for row in keyboard for button in row]

    assert labels == ["📥 Новые", "🟡 В работе", "✅ Закрытые", "👥 Все чаты", "📊 Аналитика"]


def test_closed_and_all_lists_use_compact_ticket_buttons():
    payload = {
        "scope": "closed",
        "page": 1,
        "items": [
            {
                "id": 184,
                "status_label": "🔒 Закрыто",
                "user_display_name": "R (@gergiw)",
                "status": "closed",
            }
        ],
        "has_prev": False,
        "has_next": False,
    }

    keyboard = _build_ticket_list_keyboard(payload).inline_keyboard

    assert keyboard[0][0].text.startswith("🔒 #184")
    assert keyboard[1][0].text == "🔄 Обновить"


def test_ticket_overview_keyboard_has_profile_history_and_refresh():
    ticket = {"id": 184, "support_user_id": 12, "status": "answered"}

    keyboard = _build_ticket_overview_keyboard(ticket, scope="active", page=1).inline_keyboard
    labels = [button.text for row in keyboard for button in row]

    assert "👤 Профиль" in labels
    assert "🧾 История" in labels
    assert "🔄 Обновить" in labels
    assert "✅ Закрыть" in labels


def test_admin_handler_denies_non_admin():
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=10)
    update.effective_message = SimpleNamespace(reply_text=AsyncMock())
    context = MagicMock()

    with patch(
        "bot.support_bot.load_support_bot_settings",
        return_value=SimpleNamespace(telegram_allowed_user_ids=(1, 2, 3)),
    ):
        asyncio.run(admin_handler(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(ADMIN_UNAVAILABLE_TEXT)
