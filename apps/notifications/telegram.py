from __future__ import annotations

import logging
from html import escape
from urllib.parse import urljoin

from django.conf import settings

from apps.notifications.models import Notification
from apps.users.models import TelegramAccount
from common.services.telegram_notify import TelegramNotifyError, send_telegram_message

logger = logging.getLogger(__name__)


def _get_bot_token() -> str:
    explicit = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    if explicit:
        return explicit
    return (getattr(settings, "TELEGRAM_AUTH_BOT_TOKEN", "") or "").strip()


def _platform_admin_chat_ids() -> tuple[int, ...]:
    configured = []
    raw_single = (getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", "") or "").strip()
    if raw_single:
        configured.append(int(raw_single))

    raw_many = tuple(getattr(settings, "TELEGRAM_ADMIN_CHAT_IDS", ()) or ())
    configured.extend(int(value) for value in raw_many if value)

    fallback = tuple(getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", ()) or ())
    configured.extend(int(value) for value in fallback if value)

    unique_ids = []
    for chat_id in configured:
        if chat_id not in unique_ids:
            unique_ids.append(chat_id)
    return tuple(unique_ids)


def format_notification_for_telegram(notification: Notification) -> str:
    type_icons = {
        Notification.NotificationType.INFO: "ℹ️",
        Notification.NotificationType.SUCCESS: "✅",
        Notification.NotificationType.WARNING: "⚠️",
        Notification.NotificationType.ERROR: "❌",
    }
    source = urljoin((getattr(settings, "APP_BASE_URL", "") or "").rstrip("/") + "/", notification.link.lstrip("/")) if notification.link else "сайт Sadaka"
    lines = [
        "🔔 <b>Уведомление Sadaka</b>",
        "",
        f"{type_icons.get(notification.notification_type, 'ℹ️')} <b>{escape(notification.title)}</b>",
        "",
        escape(notification.message),
    ]
    if notification.event:
        lines.extend(["", f"Событие: {escape(notification.event)}"])
    if notification.link:
        lines.extend(["", f"Открыть: {escape(source)}"])
    return "\n".join(lines)


def send_telegram_message_safe(*, chat_id: int, text: str) -> bool:
    token = _get_bot_token()
    if not token:
        logger.warning("Telegram bot token is not configured for notifications")
        return False
    try:
        send_telegram_message(bot_token=token, chat_ids=[chat_id], text=text, timeout=10)
    except TelegramNotifyError:
        logger.exception("Unable to send Telegram notification", extra={"chat_id": chat_id})
        return False
    return True


def notify_platform_admin_telegram(text: str) -> bool:
    token = _get_bot_token()
    chat_ids = _platform_admin_chat_ids()
    if not token or not chat_ids:
        logger.warning("Platform admin Telegram notifications are not configured")
        return False
    try:
        send_telegram_message(bot_token=token, chat_ids=chat_ids, text=text, timeout=10)
    except TelegramNotifyError:
        logger.exception("Unable to send Telegram notification to platform admins")
        return False
    return True


def notify_user_telegram(user, text: str) -> bool:
    try:
        account = user.telegram_account
    except TelegramAccount.DoesNotExist:
        account = None
    chat_id = getattr(account, "chat_id", None)
    if not chat_id:
        return False
    return send_telegram_message_safe(chat_id=chat_id, text=text)
