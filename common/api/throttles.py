from rest_framework.throttling import ScopedRateThrottle


class AuthBurstRateThrottle(ScopedRateThrottle):
    scope = "auth"


class TelegramStatusRateThrottle(ScopedRateThrottle):
    scope = "telegram_status"
