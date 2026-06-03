from django.conf import settings
from apps.platform.forms import AddMosqueWidgetForm


def site_meta(request):
    auth_bot_username = ((getattr(settings, "TELEGRAM_AUTH_BOT_USERNAME", "") or "").strip().lstrip("@") or "sadaka_auth_bot")
    support_bot_username = (
        (getattr(settings, "TELEGRAM_SUPPORT_USERNAME", "") or "").strip().lstrip("@")
        or (getattr(settings, "TELEGRAM_PARTNERSHIP_USERNAME", "") or "").strip().lstrip("@")
        or "sadaka_support_bot"
    )
    return {
        "site_meta": {
            "brand_name": "Садака Джария",
            "support_email": settings.DEFAULT_FROM_EMAIL,
            "telegram_support_username": support_bot_username,
            "telegram_partnership_username": support_bot_username,
            "telegram_admin_username": support_bot_username,
            "telegram_auth_username": auth_bot_username,
            "auth_bot_url": f"https://t.me/{auth_bot_username}",
            "support_bot_username": support_bot_username,
            "support_bot_url": f"https://t.me/{support_bot_username}",
        },
        "mosque_widget_form": AddMosqueWidgetForm(),
    }
