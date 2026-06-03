from django.conf import settings


class TelegramAuthProvider:
    key = "telegram"
    label = "Войти через Telegram"

    def build_deep_link(self, *, login_token: str) -> str:
        username = (getattr(settings, "TELEGRAM_AUTH_BOT_USERNAME", "") or "").strip().lstrip("@")
        if not username or not login_token:
            return ""
        return f"https://t.me/{username}?start=login_{login_token}"
