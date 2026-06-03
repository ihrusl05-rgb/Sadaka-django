from django.conf import settings


class MaxAuthProvider:
    key = "max"
    label = "Войти через MAX"

    def build_deep_link(self, *, login_token: str) -> str:
        username = (getattr(settings, "MAX_AUTH_BOT_USERNAME", "") or "").strip().lstrip("@")
        if not username or not login_token:
            return ""
        return f"https://max.ru/{username}?start=login_{login_token}"
