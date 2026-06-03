from __future__ import annotations

import logging

from asgiref.sync import sync_to_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from bot.django_bridge import get_sadaka_telegram_bot_service, get_telegram_auth_service
from bot.settings import configure_logging, load_auth_bot_settings


logger = logging.getLogger(__name__)

WELCOME_TEMPLATE = """Ассаляму алейкум!
Это официальный бот платформы Sadaka Jariya.

Здесь вы можете:
• получать коды входа
• получать уведомления
• отслеживать заявки на мечети
• узнавать статус проектов
• получать ответы от модерации

Команды:
/login — вход на сайт
/status — статус аккаунта
/notifications — последние уведомления
/requests — заявки на мечети
/projects — проекты
/help — помощь
"""

HELP_TEXT = """Команды Sadaka:
/login — начать вход или получить код, если вход уже подтверждён на сайте
/status — статус аккаунта и привязки Telegram
/notifications — последние уведомления
/requests — ваши заявки на добавление мечетей
/projects — проекты ваших мечетей или проекты, которые вы создавали
/help — список команд
"""


def _build_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔐 Вход", callback_data="bot:login"), InlineKeyboardButton("📊 Статус", callback_data="bot:status")],
            [InlineKeyboardButton("🔔 Уведомления", callback_data="bot:notifications"), InlineKeyboardButton("🕌 Заявки", callback_data="bot:requests")],
            [InlineKeyboardButton("📌 Проекты", callback_data="bot:projects"), InlineKeyboardButton("💬 Поддержка", callback_data="bot:support")],
        ]
    )


def _build_start_keyboard(settings) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Открыть сайт Sadaka", url=f"{settings.app_base_url}/login/")],
        [InlineKeyboardButton("Привязать Telegram", url=f"{settings.app_base_url}/profile/settings/")],
    ]
    rows.extend(_build_main_menu().inline_keyboard)
    return InlineKeyboardMarkup(rows)


def _support_text(settings) -> str:
    if settings.telegram_support_username:
        return (
            "Поддержка Sadaka\n\n"
            f"Для связи с командой напишите в @{settings.telegram_support_username}"
        )
    return "Поддержка Sadaka пока не настроена. Обратитесь к администратору платформы."


def _build_support_keyboard(settings) -> InlineKeyboardMarkup | None:
    if not settings.telegram_support_username:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Открыть поддержку", url=f"https://t.me/{settings.telegram_support_username}")]]
    )


def _login_restart_text(settings) -> str:
    return (
        "Чтобы войти на сайт, откройте страницу авторизации Sadaka и нажмите «Войти через Telegram».\n\n"
        f"{settings.app_base_url}/login/"
    )


def _confirm_login_and_issue_code(*, token: str, update: Update):
    telegram_auth = get_telegram_auth_service()
    login_token = telegram_auth.confirm_login_token(
        token=token,
        telegram_id=update.effective_user.id,
        chat_id=update.effective_chat.id if update.effective_chat else None,
        username=update.effective_user.username or "",
        first_name=update.effective_user.first_name or "",
        last_name=update.effective_user.last_name or "",
        auth_date=update.effective_message.date if update.effective_message else None,
    )
    telegram_auth.issue_code(login_token=login_token, user_agent="sadaka-bot")
    return login_token


def _build_status_text(*, telegram_id: int) -> str:
    service = get_sadaka_telegram_bot_service()
    payload = service.build_status_payload(telegram_id=telegram_id)
    if not payload["is_linked"]:
        return (
            "Ваш Telegram пока не привязан к аккаунту Sadaka.\n"
            "Войдите на сайт через Telegram или используйте /login после открытия страницы входа."
        )

    email_status = payload["email"] or "не указан"
    linked_at = service.format_datetime(payload["linked_at"])
    return "\n".join(
        [
            "Статус аккаунта Sadaka",
            "",
            f"Telegram: {payload['display_name']}",
            f"Привязан: {linked_at}",
            f"Email: {email_status}",
            f"Непрочитанных уведомлений: {payload['notifications_unread']}",
            f"Заявок на мечети: {payload['requests_total']}",
            f"Проектов: {payload['projects_total']}",
            f"Мечетей в управлении: {payload['managed_mosques_total']}",
        ]
    )


def _build_notifications_text(*, telegram_id: int) -> str:
    service = get_sadaka_telegram_bot_service()
    notifications = list(service.recent_notifications(telegram_id=telegram_id, limit=5))
    if not notifications:
        return "Пока нет уведомлений. Когда на платформе произойдут важные события, они появятся здесь."

    lines = ["Последние уведомления Sadaka", ""]
    for item in notifications:
        marker = "•" if item.is_read else "🔹"
        lines.extend(
            [
                f"{marker} {item.title}",
                item.message,
                f"{service.format_datetime(item.created_at)}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _build_requests_text(*, telegram_id: int) -> str:
    service = get_sadaka_telegram_bot_service()
    requests = list(service.recent_requests(telegram_id=telegram_id, limit=5))
    if not requests:
        return "Пока нет заявок на добавление мечетей, связанных с вашим аккаунтом."

    lines = ["Заявки на мечети", ""]
    for item in requests:
        lines.extend(
            [
                f"🕌 {item.mosque_name}",
                f"Статус: {item.get_status_display()}",
                f"Город: {item.city or item.region or '—'}",
                f"Дата: {service.format_datetime(item.created_at)}",
                f"Комментарий: {item.comment or '—'}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _build_projects_text(*, telegram_id: int) -> str:
    service = get_sadaka_telegram_bot_service()
    projects = list(service.recent_projects(telegram_id=telegram_id, limit=5))
    if not projects:
        return "Пока нет проектов, связанных с вашим аккаунтом или мечетями под вашим управлением."

    lines = ["Проекты", ""]
    for item in projects:
        lines.extend(
            [
                f"📌 {item.title}",
                f"Мечеть: {item.mosque.name}",
                f"Статус: {item.get_status_display()}",
                f"Собрано: {service.format_currency(item.current_amount)} ₽ из {service.format_currency(item.goal_amount)} ₽",
                f"Обновлено: {service.format_datetime(item.updated_at or item.created_at)}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _build_start_text(*, telegram_id: int) -> str:
    service = get_sadaka_telegram_bot_service()
    status = service.build_link_status(telegram_id=telegram_id)
    if status["is_linked"]:
        suffix = (
            f"Ваш Telegram привязан к аккаунту Sadaka.\n"
            f"Статус: {status['display_name']}\n"
            "Теперь вы будете получать уведомления и ответы по заявкам здесь."
        )
    else:
        suffix = (
            "Ваш Telegram пока не привязан к аккаунту Sadaka.\n"
            "Войдите на сайт через Telegram или используйте команду /login после открытия страницы входа."
        )
    return f"{WELCOME_TEMPLATE}\n{suffix}"


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_auth_bot_settings()
    payload = context.args[0] if context.args else ""

    if payload.startswith("login_"):
        token = payload.split("login_", 1)[1].strip()
        try:
            await sync_to_async(_confirm_login_and_issue_code, thread_sensitive=True)(token=token, update=update)
        except Exception as exc:
            logger.exception("Telegram login confirmation failed")
            if update.effective_message:
                await update.effective_message.reply_text(f"{exc}", reply_markup=_build_main_menu())
            return

        if update.effective_message:
            await update.effective_message.reply_text(
                "Telegram подтверждён. Код для входа отправлен в этот чат.",
                reply_markup=_build_start_keyboard(settings),
            )
        return

    if update.effective_message:
        start_text = await sync_to_async(_build_start_text, thread_sensitive=True)(
            telegram_id=update.effective_user.id
        )
        await update.effective_message.reply_text(
            start_text,
            reply_markup=_build_start_keyboard(settings),
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(HELP_TEXT, reply_markup=_build_main_menu())


async def login_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_auth_bot_settings()
    service = get_sadaka_telegram_bot_service()
    try:
        issued = await sync_to_async(service.issue_login_code_for_linked_account, thread_sensitive=True)(
            telegram_id=update.effective_user.id,
            chat_id=update.effective_chat.id if update.effective_chat else None,
            username=update.effective_user.username or "",
            first_name=update.effective_user.first_name or "",
            last_name=update.effective_user.last_name or "",
        )
    except Exception as exc:
        logger.exception("Unable to issue Sadaka login code")
        text = f"{exc}\n\n{_login_restart_text(settings)}"
    else:
        text = "Новый код входа отправлен в этот чат." if issued else _login_restart_text(settings)

    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=_build_main_menu())


async def link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_auth_bot_settings()
    text = (
        "Чтобы привязать Telegram к аккаунту Sadaka, откройте сайт и войдите через Telegram.\n\n"
        f"{settings.app_base_url}/login/"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=_build_main_menu())


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await sync_to_async(_build_status_text, thread_sensitive=True)(telegram_id=update.effective_user.id)
    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=_build_main_menu())


async def notifications_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await sync_to_async(_build_notifications_text, thread_sensitive=True)(telegram_id=update.effective_user.id)
    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=_build_main_menu())


async def requests_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await sync_to_async(_build_requests_text, thread_sensitive=True)(telegram_id=update.effective_user.id)
    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=_build_main_menu())


async def projects_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = await sync_to_async(_build_projects_text, thread_sensitive=True)(telegram_id=update.effective_user.id)
    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=_build_main_menu())


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_auth_bot_settings()
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if query.data == "bot:support":
        await query.message.reply_text(
            _support_text(settings),
            reply_markup=_build_support_keyboard(settings) or _build_main_menu(),
        )
        return

    if query.data == "bot:login":
        service = get_sadaka_telegram_bot_service()
        try:
            issued = await sync_to_async(service.issue_login_code_for_linked_account, thread_sensitive=True)(
                telegram_id=update.effective_user.id,
                chat_id=update.effective_chat.id if update.effective_chat else None,
                username=update.effective_user.username or "",
                first_name=update.effective_user.first_name or "",
                last_name=update.effective_user.last_name or "",
            )
        except Exception as exc:
            logger.exception("Unable to issue Sadaka login code")
            text = f"{exc}\n\n{_login_restart_text(settings)}"
        else:
            text = "Новый код входа отправлен в этот чат." if issued else _login_restart_text(settings)
        await query.message.reply_text(text, reply_markup=_build_main_menu())
        return

    if query.data == "bot:status":
        text = await sync_to_async(_build_status_text, thread_sensitive=True)(telegram_id=update.effective_user.id)
        await query.message.reply_text(text, reply_markup=_build_main_menu())
        return

    if query.data == "bot:notifications":
        text = await sync_to_async(_build_notifications_text, thread_sensitive=True)(telegram_id=update.effective_user.id)
        await query.message.reply_text(text, reply_markup=_build_main_menu())
        return

    if query.data == "bot:requests":
        text = await sync_to_async(_build_requests_text, thread_sensitive=True)(telegram_id=update.effective_user.id)
        await query.message.reply_text(text, reply_markup=_build_main_menu())
        return

    if query.data == "bot:projects":
        text = await sync_to_async(_build_projects_text, thread_sensitive=True)(telegram_id=update.effective_user.id)
        await query.message.reply_text(text, reply_markup=_build_main_menu())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Sadaka bot update failed", exc_info=context.error)
    tg_update = update if isinstance(update, Update) else None
    target = tg_update.effective_message or getattr(tg_update, "callback_query", None)
    if not target:
        return
    try:
        if tg_update and tg_update.callback_query and tg_update.callback_query.message:
            await tg_update.callback_query.message.reply_text(
                "Не удалось обработать команду. Попробуйте ещё раз или откройте настройки профиля на сайте.",
                reply_markup=_build_main_menu(),
            )
        elif tg_update and tg_update.effective_message:
            await tg_update.effective_message.reply_text(
                "Не удалось обработать команду. Попробуйте ещё раз или откройте настройки профиля на сайте.",
                reply_markup=_build_main_menu(),
            )
    except Exception:
        logger.exception("Sadaka bot error handler failed")


def build_application() -> Application:
    settings = load_auth_bot_settings()
    configure_logging(settings.auth_bot_log_file)
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("login", login_handler))
    application.add_handler(CommandHandler("link", link_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("notifications", notifications_handler))
    application.add_handler(CommandHandler("requests", requests_handler))
    application.add_handler(CommandHandler("projects", projects_handler))
    application.add_handler(CallbackQueryHandler(callback_handler, pattern=r"^bot:"))
    application.add_error_handler(error_handler)
    return application


def main() -> None:
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
