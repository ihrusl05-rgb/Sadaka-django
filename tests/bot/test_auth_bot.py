from bot.auth_bot import _build_main_menu


def test_auth_bot_main_menu_contains_sadaka_sections():
    keyboard = _build_main_menu().inline_keyboard
    labels = [button.text for row in keyboard for button in row]

    assert "🔐 Вход" in labels
    assert "📊 Статус" in labels
    assert "🔔 Уведомления" in labels
    assert "🕌 Заявки" in labels
    assert "📌 Проекты" in labels
    assert "💬 Поддержка" in labels
