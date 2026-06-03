from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django

    django.setup()


def get_telegram_auth_service():
    setup_django()
    from apps.users.telegram_auth import TelegramAuthService

    return TelegramAuthService


def get_sadaka_telegram_bot_service():
    setup_django()
    from apps.users.telegram_bot import SadakaTelegramBotService

    return SadakaTelegramBotService


def get_support_services():
    setup_django()
    from apps.support.services import SupportActor, SupportService

    return SupportActor, SupportService


def get_mosque_site_request_service():
    setup_django()
    from apps.platform.services import MosqueSiteRequestService

    return MosqueSiteRequestService
