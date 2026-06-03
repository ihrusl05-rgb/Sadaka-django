from __future__ import annotations

import logging
from html import escape

from django.conf import settings
from django.utils import timezone

from common.services.telegram_notify import TelegramNotifyError, send_telegram_message

logger = logging.getLogger(__name__)


class SupportNotificationError(RuntimeError):
    pass


def _support_bot_token() -> str:
    token = (getattr(settings, "TELEGRAM_SUPPORT_BOT_TOKEN", "") or "").strip()
    if not token:
        raise SupportNotificationError("TELEGRAM_SUPPORT_BOT_TOKEN is not configured.")
    return token


def _get_support_admin_ids() -> tuple[int, ...]:
    admin_ids = tuple(getattr(settings, "TELEGRAM_ADMIN_CHAT_IDS", ()) or ())
    if admin_ids:
        return admin_ids
    admin_ids = tuple(getattr(settings, "SUPPORT_ADMIN_IDS", ()) or ())
    if admin_ids:
        return admin_ids
    raise SupportNotificationError("Telegram admin chat ids are not configured.")


def _dispatch_support_message(*, text: str, reply_markup: dict | None = None) -> None:
    try:
        send_telegram_message(
            bot_token=_support_bot_token(),
            chat_ids=_get_support_admin_ids(),
            text=text,
            reply_markup=reply_markup,
        )
    except TelegramNotifyError as exc:
        raise SupportNotificationError("Unable to reach Telegram support bot API.") from exc


def _build_request_keyboard(request_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "📞 Взял заявку", "callback_data": f"mosque_request:take:{request_id}"},
                {"text": "✅ Обработано", "callback_data": f"mosque_request:approve:{request_id}"},
            ],
            [
                {"text": "🔄 Обновить", "callback_data": f"mosque_request:view:{request_id}"},
            ],
        ]
    }


def _format_request_message(request_snapshot: dict) -> str:
    now_label = timezone.localtime(request_snapshot["created_at"]).strftime("%d.%m.%Y %H:%M")
    reviewed_at = request_snapshot.get("reviewed_at")
    reviewed_label = timezone.localtime(reviewed_at).strftime("%d.%m.%Y %H:%M") if reviewed_at else "—"
    reviewer = request_snapshot.get("reviewed_by_username") or "—"
    request_id = request_snapshot["id"]
    admin_url = f"{settings.APP_BASE_URL.rstrip('/')}/admin/platform_core/mosquesiterequest/{request_id}/change/"

    location_line = request_snapshot.get("city") or request_snapshot.get("region") or "—"
    lines = [
        "🕌 <b>Заявка на добавление мечети</b>",
        "",
        f"🆔 <b>Заявка:</b> #{request_id}",
        f"📌 <b>Статус:</b> {escape(request_snapshot['status_label'])}",
        f"🗂 <b>Тип:</b> {escape(request_snapshot['request_type_label'])}",
        "",
        f"👤 <b>Заявитель:</b> {escape(request_snapshot.get('full_name') or '—')}",
        f"🕌 <b>Мечеть:</b> {escape(request_snapshot['mosque_name'])}",
        f"📍 <b>Город / регион:</b> {escape(location_line)}",
        f"📞 <b>Телефон:</b> {escape(request_snapshot['phone'])}",
        f"💬 <b>Комментарий:</b> {escape(request_snapshot.get('comment') or '—')}",
        "",
        f"🕒 <b>Создана:</b> {now_label}",
        f"👨‍💻 <b>Обработал:</b> {escape(reviewer)}",
        f"🕓 <b>Обновлена:</b> {reviewed_label}",
        f"🌐 <b>Источник:</b> {escape(request_snapshot.get('source') or 'site')}",
        f"🔗 <b>Открыть в админке:</b> {escape(admin_url)}",
    ]
    return "\n".join(lines)


def send_add_mosque_request_notification(*, request_snapshot: dict) -> None:
    text = _format_request_message(request_snapshot)
    _dispatch_support_message(text=text, reply_markup=_build_request_keyboard(request_snapshot["id"]))

    logger.info(
        "Add mosque request sent to support admins",
        extra={
            "request_id": request_snapshot["id"],
            "mosque_name": request_snapshot["mosque_name"],
            "status": request_snapshot["status"],
            "admin_count": len(_get_support_admin_ids()),
        },
    )


def send_mosque_widget_request_notification(*, request_snapshot: dict) -> None:
    _dispatch_support_message(
        text=_format_request_message(request_snapshot),
        reply_markup=_build_request_keyboard(request_snapshot["id"]),
    )
    logger.info(
        "Mosque widget request sent to support admins",
        extra={
            "request_id": request_snapshot["id"],
            "mosque_name": request_snapshot["mosque_name"],
            "status": request_snapshot["status"],
            "admin_count": len(_get_support_admin_ids()),
        },
    )
