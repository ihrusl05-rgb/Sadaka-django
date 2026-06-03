from __future__ import annotations

from html import escape
import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError
from django.utils import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.django_bridge import get_mosque_site_request_service, get_support_services
from bot.settings import TELEGRAM_MESSAGE_LIMIT, configure_logging, load_support_bot_settings
from bot.storage import (
    clear_support_admin_draft,
    get_redis_client,
    get_support_admin_draft,
    set_support_admin_draft,
)


logger = logging.getLogger(__name__)

USER_WELCOME_TEXT = (
    "Ас-саляму алейкум!\n\n"
    "Это единый бот связи команды Sadaka.\n\n"
    "Сюда можно писать по поддержке, вопросам администратору и сотрудничеству. "
    "Просто отправьте сообщение, и команда получит его."
)
USER_CLOSE_TEXT = "Ваше обращение закрыто. Если потребуется помощь — напишите снова."
ADMIN_UNAVAILABLE_TEXT = "Недоступно."
ADMIN_REPLY_PROMPT = "Введите сообщение для пользователя #{ticket_id}"
ADMIN_REPLY_SENT = "✅ Ответ отправлен"

SUPPORT_MENU_CALLBACK = "support:menu"
SUPPORT_ANALYTICS_CALLBACK = "support:analytics"


class SupportTicketDoesNotExist(Exception):
    pass


class MosqueSiteRequestDoesNotExist(Exception):
    pass


def _is_admin(settings, user_id: int | None) -> bool:
    return user_id is not None and user_id in settings.telegram_allowed_user_ids


def _actor_payload_from_update(update: Update) -> dict[str, Any]:
    user = update.effective_user
    return {
        "telegram_id": user.id,
        "username": (user.username or "").strip(),
        "first_name": (user.first_name or "").strip(),
        "last_name": (user.last_name or "").strip(),
    }


def _build_actor(payload: dict[str, Any]):
    support_actor_cls, _ = get_support_services()
    return support_actor_cls(**payload)


def _display_handle(username: str) -> str:
    return f"@{username}" if username else "—"


def _format_dt(value) -> str:
    if not value:
        return "—"
    return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")


def _shorten(text: str, limit: int = 60) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1].rstrip()}…"


def _escape_text(value: str) -> str:
    return escape(value or "")


def _message_author_label(message: dict) -> str:
    if message["sender_type"] == "user":
        return "👤 Пользователь"
    if message["sender_type"] == "admin":
        return "🛠 Админ"
    return "ℹ️ Система"


def _scope_title(scope: str) -> str:
    return {
        "new": "📥 Новые",
        "active": "🟡 В работе",
        "closed": "✅ Закрытые",
        "all": "👥 Все чаты",
    }.get(scope, "👥 Все чаты")


def _ticket_button_label(ticket: dict) -> str:
    prefix = ticket["status_label"].split(" ", 1)[0]
    label = f"{prefix} #{ticket['id']} — {ticket['user_display_name']}"
    return _shorten(label, limit=56)


def _build_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📥 Новые", callback_data="support:list:new:1")],
            [InlineKeyboardButton("🟡 В работе", callback_data="support:list:active:1")],
            [InlineKeyboardButton("✅ Закрытые", callback_data="support:list:closed:1")],
            [InlineKeyboardButton("👥 Все чаты", callback_data="support:list:all:1")],
            [InlineKeyboardButton("📊 Аналитика", callback_data=SUPPORT_ANALYTICS_CALLBACK)],
        ]
    )


def _build_ticket_list_keyboard(payload: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    scope = payload["scope"]
    page = payload["page"]

    for item in payload["items"]:
        ticket_id = item["id"]
        if scope in {"all", "closed"}:
            rows.append(
                [
                    InlineKeyboardButton(
                        _ticket_button_label(item),
                        callback_data=f"support:open:{ticket_id}:{scope}:{page}",
                    )
                ]
            )
            continue

        row = [InlineKeyboardButton("💬 Открыть", callback_data=f"support:open:{ticket_id}:{scope}:{page}")]
        if item["status"] == "new":
            row.append(InlineKeyboardButton("🟡 В работу", callback_data=f"support:take:{ticket_id}:{scope}:{page}"))
        elif item["status"] in {"in_progress", "answered"}:
            row.append(InlineKeyboardButton("✅ Закрыть", callback_data=f"support:close:{ticket_id}:{scope}:{page}"))
        rows.append(row)

    nav_row: list[InlineKeyboardButton] = []
    if payload["has_prev"]:
        nav_row.append(InlineKeyboardButton("← Назад", callback_data=f"support:list:{scope}:{page - 1}"))
    if payload["has_next"]:
        nav_row.append(InlineKeyboardButton("Дальше →", callback_data=f"support:list:{scope}:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton("🔄 Обновить", callback_data=f"support:list:{scope}:{page}")])
    rows.append([InlineKeyboardButton("⬅️ В меню", callback_data=SUPPORT_MENU_CALLBACK)])
    return InlineKeyboardMarkup(rows)


def _build_ticket_overview_keyboard(ticket: dict, *, scope: str, page: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if ticket["status"] != "closed":
        rows.append([InlineKeyboardButton("✍️ Ответить", callback_data=f"support:reply:{ticket['id']}:{scope}:{page}")])
    if ticket["status"] == "new":
        rows.append([InlineKeyboardButton("🟡 В работу", callback_data=f"support:take:{ticket['id']}:{scope}:{page}")])
    elif ticket["status"] in {"in_progress", "answered"}:
        rows.append([InlineKeyboardButton("✅ Закрыть", callback_data=f"support:close:{ticket['id']}:{scope}:{page}")])

    rows.append(
        [
            InlineKeyboardButton(
                "👤 Профиль",
                callback_data=f"support:user:{ticket['support_user_id']}:{ticket['id']}:{scope}:{page}",
            ),
            InlineKeyboardButton("🧾 История", callback_data=f"support:history:{ticket['id']}:{scope}:{page}"),
        ]
    )
    rows.append([InlineKeyboardButton("🔄 Обновить", callback_data=f"support:open:{ticket['id']}:{scope}:{page}")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"support:list:{scope}:{page}")])
    return InlineKeyboardMarkup(rows)


def _build_ticket_history_keyboard(ticket: dict, *, scope: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👤 Профиль",
                    callback_data=f"support:user:{ticket['support_user_id']}:{ticket['id']}:{scope}:{page}",
                ),
                InlineKeyboardButton("🔄 Обновить", callback_data=f"support:history:{ticket['id']}:{scope}:{page}"),
            ],
            [InlineKeyboardButton("⬅️ К обращению", callback_data=f"support:open:{ticket['id']}:{scope}:{page}")],
        ]
    )


def _build_profile_keyboard(profile: dict, *, ticket_id: int, scope: str, page: int) -> InlineKeyboardMarkup:
    block_label = "✅ Разблокировать" if profile["is_blocked"] else "🚫 Заблокировать"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    block_label,
                    callback_data=f"support:block:{profile['support_user_id']}:{ticket_id}:{scope}:{page}",
                ),
                InlineKeyboardButton(
                    "🔄 Обновить",
                    callback_data=f"support:user:{profile['support_user_id']}:{ticket_id}:{scope}:{page}",
                ),
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"support:open:{ticket_id}:{scope}:{page}")],
        ]
    )


def _build_analytics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Обновить", callback_data=SUPPORT_ANALYTICS_CALLBACK)],
            [InlineKeyboardButton("⬅️ В меню", callback_data=SUPPORT_MENU_CALLBACK)],
        ]
    )


def _is_refresh_callback(data: str) -> bool:
    if data == SUPPORT_ANALYTICS_CALLBACK:
        return True
    if data.startswith("mosque_request:view:"):
        return True
    parts = data.split(":")
    if len(parts) >= 2 and parts[:2] == ["support", "list"]:
        return True
    if len(parts) >= 2 and tuple(parts[:2]) in {("support", "open"), ("support", "history"), ("support", "user")}:
        return True
    return False


def _format_ticket_list(payload: dict) -> str:
    lines = [f"{_scope_title(payload['scope'])}\n"]
    if not payload["items"]:
        lines.append("Список пуст.")
        return "\n".join(lines)

    if payload["scope"] in {"all", "closed"}:
        lines.append("Выберите обращение из списка ниже.")
        return "\n".join(lines)

    for item in payload["items"]:
        lines.extend(
            [
                f"📩 #{item['id']} — {item['user_display_name']}",
                item["status_label"],
                f"💬 {_shorten(item['last_message'] or '—')}",
                f"🕒 {_format_dt(item['last_message_at'])}",
                "✅ Ответ администратора: да" if item["has_admin_reply"] else "⌛ Без ответа",
            ]
        )
        if item["assigned_admin_id"]:
            lines.append(f"👨‍💻 В работе: {item['assigned_admin_label']}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_ticket_overview(ticket: dict) -> str:
    lines = [
        f"📩 <b>Обращение #{ticket['id']}</b>",
        "",
        f"👤 <b>{_escape_text(ticket['user_display_name'])}</b>",
        f"🔗 {_escape_text(_display_handle(ticket['username']))}",
        f"🆔 <code>{ticket['telegram_user_id']}</code>",
        "",
        f"📌 Статус: <b>{_escape_text(ticket['status_label'])}</b>",
        f"🕒 {_format_dt(ticket['updated_at'])}",
    ]
    if ticket["assigned_admin_id"]:
        lines.append(f"👨‍💻 В работе: <b>{_escape_text(ticket['assigned_admin_label'])}</b>")
    lines.extend(
        [
            "",
            "Последнее сообщение:",
            f"<blockquote>{_escape_text(ticket['last_message'] or '—')}</blockquote>",
        ]
    )
    return "\n".join(lines)[:TELEGRAM_MESSAGE_LIMIT]


def _format_ticket_history(ticket: dict) -> str:
    lines = [
        f"🧾 <b>История обращения #{ticket['id']}</b>",
        "",
        f"👤 <b>{_escape_text(ticket['user_display_name'])}</b>",
        f"📌 {_escape_text(ticket['status_label'])}",
        "",
    ]

    messages = ticket["messages"]
    if len(messages) > 20:
        lines.append("… Показаны последние 20 сообщений")
        lines.append("")
        messages = messages[-20:]

    for message in messages:
        lines.append(f"<b>{_escape_text(_message_author_label(message))}</b> · {_format_dt(message['created_at'])}")
        lines.append(f"<blockquote>{_escape_text(message['text'])}</blockquote>")
        lines.append("")

    return "\n".join(lines).strip()[:TELEGRAM_MESSAGE_LIMIT]


def _format_user_profile(profile: dict) -> str:
    return "\n".join(
        [
            "👤 <b>Профиль пользователя</b>",
            "",
            f"🆔 <code>{profile['telegram_user_id']}</code>",
            f"Имя: <b>{_escape_text(profile['display_name'])}</b>",
            f"Username: {_escape_text(_display_handle(profile['username']))}",
            f"Первое обращение: {_format_dt(profile['first_seen_at'])}",
            f"Всего обращений: <b>{profile['tickets_total']}</b>",
            f"Открытых: <b>{profile['open_tickets_total']}</b>",
            f"Закрытых: <b>{profile['closed_tickets_total']}</b>",
            f"Последнее сообщение: <blockquote>{_escape_text(profile['last_message'] or '—')}</blockquote>",
            f"Заблокирован: <b>{'да' if profile['is_blocked'] else 'нет'}</b>",
        ]
    )


def _format_analytics(payload: dict) -> str:
    top_users_lines = ["<b>Топ пользователей:</b>"]
    if payload["top_users"]:
        for item in payload["top_users"]:
            top_users_lines.append(f"— {_escape_text(item['display_name'])} — <b>{item['tickets_total']}</b>")
    else:
        top_users_lines.append("— пока нет данных")

    _, support_service = get_support_services()
    return "\n".join(
        [
            "📊 <b>Аналитика поддержки</b>",
            "",
            "<b>Сегодня:</b>",
            f"— новых обращений: <b>{payload['today']['new']}</b>",
            f"— отвечено: <b>{payload['today']['answered']}</b>",
            f"— закрыто: <b>{payload['today']['closed']}</b>",
            "",
            "<b>Всего:</b>",
            f"— обращений: <b>{payload['totals']['all']}</b>",
            f"— открытых: <b>{payload['totals']['open']}</b>",
            f"— в работе: <b>{payload['totals']['in_progress']}</b>",
            f"— отвечено: <b>{payload['totals']['answered']}</b>",
            f"— закрытых: <b>{payload['totals']['closed']}</b>",
            "",
            f"Среднее время ответа: <b>{support_service.format_duration(payload['average_response_seconds'])}</b>",
            "",
            *top_users_lines,
        ]
    )


def _build_mosque_request_keyboard(request_snapshot: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    request_id = request_snapshot["id"]
    status = request_snapshot["status"]

    if status == "new":
        rows.append(
            [
                InlineKeyboardButton("📞 Взял заявку", callback_data=f"mosque_request:take:{request_id}"),
                InlineKeyboardButton("✅ Обработано", callback_data=f"mosque_request:approve:{request_id}"),
            ]
        )
    elif status == "in_progress":
        rows.append(
            [
                InlineKeyboardButton("✅ Обработано", callback_data=f"mosque_request:approve:{request_id}"),
                InlineKeyboardButton("↩️ Вернуть в новые", callback_data=f"mosque_request:reset:{request_id}"),
            ]
        )
    else:
        rows.append([InlineKeyboardButton("↩️ Вернуть в новые", callback_data=f"mosque_request:reset:{request_id}")])

    rows.append([InlineKeyboardButton("🔄 Обновить", callback_data=f"mosque_request:view:{request_id}")])
    return InlineKeyboardMarkup(rows)


def _format_mosque_request(request_snapshot: dict) -> str:
    location = request_snapshot.get("city") or request_snapshot.get("region") or "—"
    reviewer = request_snapshot.get("reviewed_by_username") or "—"
    reviewed_at = _format_dt(request_snapshot.get("reviewed_at"))

    return "\n".join(
        [
            "🕌 <b>Заявка на добавление мечети</b>",
            "",
            f"🆔 <b>Заявка:</b> #{request_snapshot['id']}",
            f"📌 <b>Статус:</b> {_escape_text(request_snapshot['status_label'])}",
            f"🗂 <b>Тип:</b> {_escape_text(request_snapshot['request_type_label'])}",
            "",
            f"👤 <b>Заявитель:</b> {_escape_text(request_snapshot.get('full_name') or '—')}",
            f"🕌 <b>Мечеть:</b> {_escape_text(request_snapshot['mosque_name'])}",
            f"📍 <b>Город / регион:</b> {_escape_text(location)}",
            f"📞 <b>Телефон:</b> {_escape_text(request_snapshot['phone'])}",
            f"💬 <b>Комментарий:</b> {_escape_text(request_snapshot.get('comment') or '—')}",
            "",
            f"🕒 <b>Создана:</b> {_format_dt(request_snapshot['created_at'])}",
            f"👨‍💻 <b>Обработал:</b> {_escape_text(reviewer)}",
            f"🕓 <b>Обновлена:</b> {reviewed_at}",
        ]
    )[:TELEGRAM_MESSAGE_LIMIT]


def _sync_receive_user_message(actor_payload: dict[str, Any], text: str) -> dict:
    actor = _build_actor(actor_payload)
    _, support_service = get_support_services()
    ticket, _, created_ticket = support_service.receive_user_message(actor=actor, text=text)
    snapshot = support_service.get_ticket_snapshot(ticket_id=ticket.id)
    return {"ticket": snapshot, "created_ticket": created_ticket}


def _sync_list_tickets(scope: str, page: int) -> dict:
    _, support_service = get_support_services()
    return support_service.list_tickets(scope=scope, page=page)


def _sync_get_ticket(ticket_id: int) -> dict:
    _, support_service = get_support_services()
    try:
        return support_service.get_ticket_snapshot(ticket_id=ticket_id)
    except Exception as exc:
        if exc.__class__.__name__ == "DoesNotExist":
            raise SupportTicketDoesNotExist from exc
        raise


def _sync_assign_ticket(ticket_id: int, actor_payload: dict[str, Any]) -> dict:
    actor = _build_actor(actor_payload)
    _, support_service = get_support_services()
    try:
        ticket = support_service.get_ticket(ticket_id=ticket_id)
    except Exception as exc:
        if exc.__class__.__name__ == "DoesNotExist":
            raise SupportTicketDoesNotExist from exc
        raise
    support_service.assign_ticket(ticket=ticket, admin=actor)
    return support_service.get_ticket_snapshot(ticket_id=ticket_id)


def _sync_close_ticket(ticket_id: int, actor_payload: dict[str, Any]) -> dict:
    actor = _build_actor(actor_payload)
    _, support_service = get_support_services()
    try:
        ticket = support_service.get_ticket(ticket_id=ticket_id)
    except Exception as exc:
        if exc.__class__.__name__ == "DoesNotExist":
            raise SupportTicketDoesNotExist from exc
        raise
    support_service.close_ticket(ticket=ticket, admin=actor)
    return support_service.get_ticket_snapshot(ticket_id=ticket_id)


def _sync_send_admin_reply(ticket_id: int, actor_payload: dict[str, Any], text: str) -> dict:
    actor = _build_actor(actor_payload)
    _, support_service = get_support_services()
    try:
        ticket = support_service.get_ticket(ticket_id=ticket_id)
    except Exception as exc:
        if exc.__class__.__name__ == "DoesNotExist":
            raise SupportTicketDoesNotExist from exc
        raise
    support_service.send_admin_reply(ticket=ticket, admin=actor, text=text)
    return support_service.get_ticket_snapshot(ticket_id=ticket_id)


def _sync_get_user_profile(support_user_id: int) -> dict:
    _, support_service = get_support_services()
    try:
        return support_service.get_user_profile(support_user_id=support_user_id)
    except Exception as exc:
        if exc.__class__.__name__ == "DoesNotExist":
            raise SupportTicketDoesNotExist from exc
        raise


def _sync_toggle_user_block(support_user_id: int) -> dict:
    _, support_service = get_support_services()
    try:
        return support_service.toggle_user_block_by_id(support_user_id=support_user_id)
    except Exception as exc:
        if exc.__class__.__name__ == "DoesNotExist":
            raise SupportTicketDoesNotExist from exc
        raise


def _sync_get_analytics() -> dict:
    _, support_service = get_support_services()
    return support_service.get_analytics()


def _sync_get_mosque_request(request_id: int) -> dict:
    mosque_request_service = get_mosque_site_request_service()
    try:
        return mosque_request_service.get_snapshot(request_id=request_id)
    except Exception as exc:
        if exc.__class__.__name__ == "DoesNotExist":
            raise MosqueSiteRequestDoesNotExist from exc
        raise


def _sync_update_mosque_request_status(request_id: int, status: str, actor_payload: dict[str, Any]) -> dict:
    mosque_request_service = get_mosque_site_request_service()
    try:
        return mosque_request_service.set_status(
            request_id=request_id,
            status=status,
            admin_telegram_id=actor_payload.get("telegram_id"),
            admin_username=actor_payload.get("username") or "",
        )
    except Exception as exc:
        if exc.__class__.__name__ == "DoesNotExist":
            raise MosqueSiteRequestDoesNotExist from exc
        raise


async def _notify_admins(context: ContextTypes.DEFAULT_TYPE, ticket: dict) -> None:
    settings = load_support_bot_settings()
    if not settings.telegram_allowed_user_ids:
        logger.warning("Support admin list is empty; ticket #%s was not broadcast", ticket["id"])
        return

    text = "\n".join(
        [
            f"📩 Новое обращение #{ticket['id']}",
            f"👤 {ticket['user_display_name']}",
            f"🔗 {_display_handle(ticket['username'])}",
            f"💬 {_shorten(ticket['last_message'] or '—', limit=120)}",
            f"🕒 {_format_dt(ticket['last_message_at'])}",
        ]
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💬 Открыть", callback_data=f"support:open:{ticket['id']}:all:1"),
                InlineKeyboardButton("🟡 В работу", callback_data=f"support:take:{ticket['id']}:all:1"),
            ]
        ]
    )

    for admin_id in settings.telegram_allowed_user_ids:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, reply_markup=keyboard)
        except Exception:
            logger.exception("Unable to deliver support notification to admin_id=%s", admin_id)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    settings = load_support_bot_settings()
    if _is_admin(settings, update.effective_user.id if update.effective_user else None):
        await message.reply_text("Панель поддержки Sadaka доступна по команде /admin")
        return

    await message.reply_text(USER_WELCOME_TEXT)


async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    settings = load_support_bot_settings()
    if not _is_admin(settings, update.effective_user.id if update.effective_user else None):
        await message.reply_text(ADMIN_UNAVAILABLE_TEXT)
        return

    await message.reply_text("Панель поддержки Sadaka", reply_markup=_build_main_menu())


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_handler(update, context)


async def _show_menu(query) -> None:
    await _safe_edit_message(query, "Панель поддержки Sadaka", reply_markup=_build_main_menu())


async def _show_ticket_list(query, scope: str, page: int) -> None:
    payload = await sync_to_async(_sync_list_tickets, thread_sensitive=True)(scope, page)
    await _safe_edit_message(query, _format_ticket_list(payload), reply_markup=_build_ticket_list_keyboard(payload))


async def _show_ticket_overview(query, ticket_id: int, scope: str, page: int) -> None:
    ticket = await sync_to_async(_sync_get_ticket, thread_sensitive=True)(ticket_id)
    await _safe_edit_message(
        query,
        _format_ticket_overview(ticket),
        reply_markup=_build_ticket_overview_keyboard(ticket, scope=scope, page=page),
        parse_mode=ParseMode.HTML,
    )


async def _show_ticket_history(query, ticket_id: int, scope: str, page: int) -> None:
    ticket = await sync_to_async(_sync_get_ticket, thread_sensitive=True)(ticket_id)
    await _safe_edit_message(
        query,
        _format_ticket_history(ticket),
        reply_markup=_build_ticket_history_keyboard(ticket, scope=scope, page=page),
        parse_mode=ParseMode.HTML,
    )


async def _show_user_profile(query, support_user_id: int, ticket_id: int, scope: str, page: int) -> None:
    profile = await sync_to_async(_sync_get_user_profile, thread_sensitive=True)(support_user_id)
    await _safe_edit_message(
        query,
        _format_user_profile(profile),
        reply_markup=_build_profile_keyboard(profile, ticket_id=ticket_id, scope=scope, page=page),
        parse_mode=ParseMode.HTML,
    )


async def _show_analytics(query) -> None:
    payload = await sync_to_async(_sync_get_analytics, thread_sensitive=True)()
    await _safe_edit_message(
        query,
        _format_analytics(payload),
        reply_markup=_build_analytics_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def _show_mosque_request(query, request_id: int) -> None:
    request_snapshot = await sync_to_async(_sync_get_mosque_request, thread_sensitive=True)(request_id)
    await _safe_edit_message(
        query,
        _format_mosque_request(request_snapshot),
        reply_markup=_build_mosque_request_keyboard(request_snapshot),
        parse_mode=ParseMode.HTML,
    )


async def _safe_edit_message(query, text: str, *, reply_markup: InlineKeyboardMarkup | None = None, parse_mode=None) -> None:
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return
        raise


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    data = query.data or ""

    settings = load_support_bot_settings()
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_admin(settings, user_id):
        await query.answer(ADMIN_UNAVAILABLE_TEXT, show_alert=True)
        return

    if _is_refresh_callback(data):
        await query.answer("Обновлено")
    else:
        await query.answer()
    parts = data.split(":")

    try:
        if data == SUPPORT_MENU_CALLBACK:
            await _show_menu(query)
            return

        if data == SUPPORT_ANALYTICS_CALLBACK:
            await _show_analytics(query)
            return

        if len(parts) == 3 and parts[:2] == ["mosque_request", "view"]:
            await _show_mosque_request(query, int(parts[2]))
            return

        if len(parts) == 3 and parts[:2] == ["mosque_request", "take"]:
            request_snapshot = await sync_to_async(_sync_update_mosque_request_status, thread_sensitive=True)(
                int(parts[2]),
                "in_progress",
                _actor_payload_from_update(update),
            )
            await _safe_edit_message(
                query,
                _format_mosque_request(request_snapshot),
                reply_markup=_build_mosque_request_keyboard(request_snapshot),
                parse_mode=ParseMode.HTML,
            )
            return

        if len(parts) == 3 and parts[:2] == ["mosque_request", "approve"]:
            request_snapshot = await sync_to_async(_sync_update_mosque_request_status, thread_sensitive=True)(
                int(parts[2]),
                "approved",
                _actor_payload_from_update(update),
            )
            await _safe_edit_message(
                query,
                _format_mosque_request(request_snapshot),
                reply_markup=_build_mosque_request_keyboard(request_snapshot),
                parse_mode=ParseMode.HTML,
            )
            return

        if len(parts) == 3 and parts[:2] == ["mosque_request", "reset"]:
            request_snapshot = await sync_to_async(_sync_update_mosque_request_status, thread_sensitive=True)(
                int(parts[2]),
                "new",
                _actor_payload_from_update(update),
            )
            await _safe_edit_message(
                query,
                _format_mosque_request(request_snapshot),
                reply_markup=_build_mosque_request_keyboard(request_snapshot),
                parse_mode=ParseMode.HTML,
            )
            return

        if len(parts) == 3 and parts[:2] == ["mosque_request", "reject"]:
            await query.answer("Кнопка больше не используется. Отметьте заявку как «Взял заявку» или «Обработано».", show_alert=True)
            return

        if len(parts) == 4 and parts[:2] == ["support", "list"]:
            await _show_ticket_list(query, parts[2], int(parts[3]))
            return

        if len(parts) == 5 and parts[:2] == ["support", "open"]:
            await _show_ticket_overview(query, int(parts[2]), parts[3], int(parts[4]))
            return

        if len(parts) == 5 and parts[:2] == ["support", "history"]:
            await _show_ticket_history(query, int(parts[2]), parts[3], int(parts[4]))
            return

        if len(parts) == 5 and parts[:2] == ["support", "take"]:
            ticket = await sync_to_async(_sync_assign_ticket, thread_sensitive=True)(
                int(parts[2]),
                _actor_payload_from_update(update),
            )
            await _safe_edit_message(
                query,
                _format_ticket_overview(ticket),
                reply_markup=_build_ticket_overview_keyboard(ticket, scope=parts[3], page=int(parts[4])),
                parse_mode=ParseMode.HTML,
            )
            return

        if len(parts) == 5 and parts[:2] == ["support", "close"]:
            ticket = await sync_to_async(_sync_close_ticket, thread_sensitive=True)(
                int(parts[2]),
                _actor_payload_from_update(update),
            )
            try:
                await context.bot.send_message(chat_id=ticket["telegram_user_id"], text=USER_CLOSE_TEXT)
            except Exception:
                logger.exception("Unable to send close notice for ticket_id=%s", ticket["id"])
            await _safe_edit_message(
                query,
                _format_ticket_overview(ticket),
                reply_markup=_build_ticket_overview_keyboard(ticket, scope=parts[3], page=int(parts[4])),
                parse_mode=ParseMode.HTML,
            )
            return

        if len(parts) == 5 and parts[:2] == ["support", "reply"]:
            redis_client = get_redis_client(settings)
            set_support_admin_draft(
                redis_client,
                admin_telegram_id=user_id,
                ticket_id=int(parts[2]),
            )
            await query.message.reply_text(ADMIN_REPLY_PROMPT.format(ticket_id=parts[2]))
            return

        if len(parts) == 6 and parts[:2] == ["support", "user"]:
            await _show_user_profile(query, int(parts[2]), int(parts[3]), parts[4], int(parts[5]))
            return

        if len(parts) == 6 and parts[:2] == ["support", "block"]:
            profile = await sync_to_async(_sync_toggle_user_block, thread_sensitive=True)(int(parts[2]))
            await _safe_edit_message(
                query,
                _format_user_profile(profile),
                reply_markup=_build_profile_keyboard(profile, ticket_id=int(parts[3]), scope=parts[4], page=int(parts[5])),
                parse_mode=ParseMode.HTML,
            )
            return
    except SupportTicketDoesNotExist:
        await _safe_edit_message(query, "Обращение не найдено.", reply_markup=_build_main_menu())
        return
    except MosqueSiteRequestDoesNotExist:
        await query.message.reply_text("Заявка не найдена.")
        return
    except ValidationError as exc:
        await query.message.reply_text(str(exc))
        return
    except Exception:
        logger.exception("Support callback handler failed for data=%s", data)
        await query.message.reply_text("Не удалось обработать действие. Попробуйте ещё раз.")
        return

    await query.message.reply_text("Не удалось обработать действие.")


async def _handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not update.effective_user:
        return

    settings = load_support_bot_settings()
    redis_client = get_redis_client(settings)
    draft = get_support_admin_draft(redis_client, admin_telegram_id=update.effective_user.id)
    if not draft:
        await message.reply_text("Откройте /admin и выберите обращение, чтобы ответить пользователю.")
        return

    ticket_id = int(draft["ticket_id"])
    text = (message.text or message.caption or "").strip()
    if not text:
        await message.reply_text("Введите текстовое сообщение для пользователя.")
        return

    try:
        ticket = await sync_to_async(_sync_get_ticket, thread_sensitive=True)(ticket_id)
    except Exception:
        logger.exception("Unable to load support ticket_id=%s before reply", ticket_id)
        await message.reply_text("Не удалось открыть обращение.")
        return

    try:
        await context.bot.send_message(chat_id=ticket["telegram_user_id"], text=text)
    except Exception:
        logger.exception("Unable to deliver admin reply to ticket_id=%s", ticket_id)
        await message.reply_text("Не удалось отправить сообщение пользователю.")
        return

    try:
        await sync_to_async(_sync_send_admin_reply, thread_sensitive=True)(
            ticket_id,
            _actor_payload_from_update(update),
            text,
        )
    except ValidationError as exc:
        await message.reply_text(str(exc))
        return
    except Exception:
        logger.exception("Unable to persist support admin reply for ticket_id=%s", ticket_id)
        await message.reply_text("Сообщение пользователю отправлено, но не удалось сохранить ответ в системе.")
        return

    clear_support_admin_draft(redis_client, admin_telegram_id=update.effective_user.id)
    await message.reply_text(ADMIN_REPLY_SENT)


async def _handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not update.effective_user:
        return

    chat = update.effective_chat
    if not chat or chat.type != "private":
        await message.reply_text("Для связи с командой Sadaka напишите боту в личные сообщения.")
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.reply_text("Пока можно отправить только текстовое сообщение.")
        return

    try:
        result = await sync_to_async(_sync_receive_user_message, thread_sensitive=True)(
            _actor_payload_from_update(update),
            text,
        )
    except ValidationError as exc:
        await message.reply_text(str(exc))
        return
    except Exception:
        logger.exception("Unable to store support message from user_id=%s", update.effective_user.id)
        await message.reply_text("Не удалось отправить сообщение. Попробуйте ещё раз позже.")
        return

    await _notify_admins(context, result["ticket"])


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_chat:
        return
    if update.effective_user and update.effective_user.is_bot:
        return

    settings = load_support_bot_settings()
    if _is_admin(settings, update.effective_user.id if update.effective_user else None):
        await _handle_admin_message(update, context)
        return

    await _handle_user_message(update, context)


def build_application() -> Application:
    settings = load_support_bot_settings()
    configure_logging(settings.support_bot_log_file)
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("admin", admin_handler))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern=r"^(support|mosque_request):"))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))
    return application


def main() -> None:
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
