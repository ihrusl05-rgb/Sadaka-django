from __future__ import annotations

import logging
import os
import random
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from telegram import Bot

from apps.platform.services import AuditLogService
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.users.auth_providers.telegram import TelegramAuthProvider
from apps.users.models import TelegramAccount, TelegramAuthCode, TelegramLoginToken, User
from apps.users.services import UserService

logger = logging.getLogger(__name__)


@dataclass
class TelegramLoginTokenResult:
    login_token: TelegramLoginToken
    telegram_url: str


@dataclass
class TelegramLoginStatus:
    login_token: TelegramLoginToken
    status: str
    telegram_url: str
    display_name: str = ""
    debug_code: str | None = None


@dataclass
class TelegramCodeIssueResult:
    auth_code: TelegramAuthCode
    raw_code: str
    debug_code: str | None = None


@dataclass
class TelegramIdentity:
    telegram_id: int
    chat_id: int | None = None
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    photo_url: str = ""
    auth_date: datetime | None = None


class TelegramAuthService:
    CODE_TTL_SECONDS = 5 * 60
    MAX_ATTEMPTS = 5

    @staticmethod
    def _login_token_ttl_seconds() -> int:
        return int(getattr(settings, "TELEGRAM_LOGIN_TOKEN_TTL_SECONDS", 300))

    @staticmethod
    def _is_debug_mode() -> bool:
        return bool(settings.DEBUG or os.environ.get("PYTEST_CURRENT_TEST"))

    @staticmethod
    def _trim_user_agent(user_agent: str | None) -> str:
        return (user_agent or "").strip()[:255]

    @staticmethod
    def _build_placeholder_email(telegram_id: int) -> str:
        return f"telegram_{telegram_id}@{User.TELEGRAM_AUTH_EMAIL_DOMAIN}"

    @staticmethod
    def _debug_cache_key(*, token: str | None = None, telegram_id: int | None = None) -> str:
        if token:
            return f"auth:telegram:debug:token:{token}"
        return f"auth:telegram:debug:tg:{telegram_id}"

    @staticmethod
    def _store_debug_code(*, code: str, login_token: TelegramLoginToken | None, telegram_id: int) -> None:
        if not TelegramAuthService._is_debug_mode():
            return
        timeout = TelegramAuthService.CODE_TTL_SECONDS
        if login_token is not None:
            cache.set(TelegramAuthService._debug_cache_key(token=login_token.token), code, timeout=timeout)
        cache.set(TelegramAuthService._debug_cache_key(telegram_id=telegram_id), code, timeout=timeout)

    @staticmethod
    def _get_debug_code(*, login_token: TelegramLoginToken | None = None, telegram_id: int | None = None) -> str | None:
        if not TelegramAuthService._is_debug_mode():
            return None
        if login_token is not None:
            return cache.get(TelegramAuthService._debug_cache_key(token=login_token.token))
        if telegram_id is not None:
            return cache.get(TelegramAuthService._debug_cache_key(telegram_id=telegram_id))
        return None

    @staticmethod
    def _build_display_name(account: TelegramAccount) -> str:
        if account.username:
            return f"@{account.username}"
        full_name = User.build_full_name(last_name=account.last_name, first_name=account.first_name).strip()
        if full_name:
            return full_name
        return str(account.telegram_id)

    @staticmethod
    def _can_transfer_existing_account(*, existing_owner: User) -> bool:
        if User.is_placeholder_email(existing_owner.email):
            return True
        return not existing_owner.has_usable_password()

    @staticmethod
    def build_login_code_message(*, code: str) -> str:
        return "\n".join(
            [
                "🔐 Код входа в Sadaka",
                "",
                f"Ваш код: {code}",
                "",
                "Код действует 5 минут.",
                "Если это были не вы, просто проигнорируйте сообщение.",
            ]
        )

    @staticmethod
    def _send_code_via_bot(*, account: TelegramAccount, code: str) -> None:
        if not account.chat_id:
            raise ValidationError("Telegram-чат не привязан. Откройте бота по ссылке со страницы входа.")

        bot_token = (getattr(settings, "TELEGRAM_AUTH_BOT_TOKEN", "") or "").strip()
        if not bot_token:
            if TelegramAuthService._is_debug_mode():
                return
            raise ValidationError("TELEGRAM_AUTH_BOT_TOKEN не настроен.")

        bot = Bot(token=bot_token)
        try:
            async_to_sync(bot.send_message)(
                chat_id=account.chat_id,
                text=TelegramAuthService.build_login_code_message(code=code),
            )
        except Exception as exc:
            logger.exception(
                "Failed to send Telegram auth code",
                extra={"telegram_id": account.telegram_id, "chat_id": account.chat_id},
            )
            raise ValidationError("Не удалось отправить код в Telegram. Попробуйте еще раз.") from exc

    @staticmethod
    def _get_login_token(*, token: str) -> TelegramLoginToken:
        login_token = (
            TelegramLoginToken.objects.select_related("user", "telegram_account", "telegram_account__user")
            .filter(token=token)
            .first()
        )
        if not login_token:
            raise ValidationError("Не удалось подтвердить Telegram. Попробуйте ещё раз.")
        return login_token

    @staticmethod
    def _get_or_create_user(identity: TelegramIdentity) -> tuple[User, TelegramAccount]:
        account = TelegramAccount.objects.select_related("user").filter(telegram_id=identity.telegram_id).first()

        if account:
            update_fields = ["updated_at"]
            if identity.chat_id and account.chat_id != identity.chat_id:
                account.chat_id = identity.chat_id
                update_fields.append("chat_id")
            for field_name, value in (
                ("username", identity.username),
                ("first_name", identity.first_name),
                ("last_name", identity.last_name),
                ("photo_url", identity.photo_url),
            ):
                value = (value or "").strip()
                if getattr(account, field_name) != value:
                    setattr(account, field_name, value)
                    update_fields.append(field_name)
            if identity.auth_date and account.auth_date != identity.auth_date:
                account.auth_date = identity.auth_date
                update_fields.append("auth_date")
            account.save(update_fields=update_fields)

            user = account.user
            user_update_fields = ["updated_at"]
            if not user.first_name and account.first_name:
                user.first_name = account.first_name
                user_update_fields.append("first_name")
            if not user.last_name and account.last_name:
                user.last_name = account.last_name
                user_update_fields.append("last_name")
            if len(user_update_fields) > 1:
                user.full_name = User.build_full_name(last_name=user.last_name, first_name=user.first_name)
                user_update_fields.append("full_name")
                user.save(update_fields=user_update_fields)
            return user, account

        user = User.objects.create_user(
            email=TelegramAuthService._build_placeholder_email(identity.telegram_id),
            password=None,
            first_name=(identity.first_name or "").strip(),
            last_name=(identity.last_name or "").strip(),
            full_name=User.build_full_name(
                last_name=(identity.last_name or "").strip(),
                first_name=(identity.first_name or "").strip(),
            ),
        )
        account = TelegramAccount.objects.create(
            user=user,
            telegram_id=identity.telegram_id,
            chat_id=identity.chat_id,
            username=(identity.username or "").strip(),
            first_name=(identity.first_name or "").strip(),
            last_name=(identity.last_name or "").strip(),
            photo_url=(identity.photo_url or "").strip(),
            auth_date=identity.auth_date,
            linked_at=timezone.now(),
        )
        AuditLogService.log(
            action="user.telegram_linked",
            obj=user,
            metadata={"telegram_id": identity.telegram_id, "username": account.username},
        )
        NotificationService.notify_platform_admins(
            title="Новый пользователь зарегистрирован",
            message=f"Пользователь {TelegramAuthService._build_display_name(account)} вошел через Telegram.",
            event=Notification.Event.NEW_USER_REGISTERED,
            notification_type=Notification.NotificationType.INFO,
            link="/admin/users/user/",
            payload={"user_id": user.id, "telegram_id": identity.telegram_id},
        )
        return user, account

    @staticmethod
    def _bind_account_to_user(*, user: User, identity: TelegramIdentity) -> tuple[User, TelegramAccount]:
        existing_account = TelegramAccount.objects.select_related("user").filter(telegram_id=identity.telegram_id).first()
        current_account = TelegramAccount.objects.select_related("user").filter(user=user).first()
        transferred_account = False

        if current_account and current_account.telegram_id != identity.telegram_id:
            raise ValidationError("К вашему профилю уже привязан другой Telegram-аккаунт.")

        if existing_account and existing_account.user_id != user.id:
            existing_owner = existing_account.user
            if not TelegramAuthService._can_transfer_existing_account(existing_owner=existing_owner):
                raise ValidationError("Этот Telegram уже привязан к другому аккаунту Sadaka.")
            existing_account.user = user
            existing_account.linked_at = timezone.now()
            transferred_account = True

        account = existing_account or current_account
        if account is None:
            account = TelegramAccount(user=user, telegram_id=identity.telegram_id, linked_at=timezone.now())

        update_fields = ["updated_at"]
        if account.chat_id != identity.chat_id and identity.chat_id:
            account.chat_id = identity.chat_id
            update_fields.append("chat_id")
        for field_name, value in (
            ("username", identity.username),
            ("first_name", identity.first_name),
            ("last_name", identity.last_name),
            ("photo_url", identity.photo_url),
        ):
            value = (value or "").strip()
            if getattr(account, field_name) != value:
                setattr(account, field_name, value)
                update_fields.append(field_name)
        if identity.auth_date and account.auth_date != identity.auth_date:
            account.auth_date = identity.auth_date
            update_fields.append("auth_date")

        if account.pk is None:
            account.save()
        else:
            if account.user_id != user.id:
                account.user = user
                update_fields.append("user")
            if transferred_account:
                update_fields.extend(["user", "linked_at"])
            account.save(update_fields=list(dict.fromkeys(update_fields)))

        user_update_fields = ["updated_at"]
        if not user.first_name and account.first_name:
            user.first_name = account.first_name
            user_update_fields.append("first_name")
        if not user.last_name and account.last_name:
            user.last_name = account.last_name
            user_update_fields.append("last_name")
        if len(user_update_fields) > 1:
            user.full_name = User.build_full_name(last_name=user.last_name, first_name=user.first_name)
            user_update_fields.append("full_name")
            user.save(update_fields=user_update_fields)

        AuditLogService.log(
            action="user.telegram_linked",
            obj=user,
            metadata={"telegram_id": identity.telegram_id, "username": account.username},
        )
        return user, account

    @staticmethod
    def create_login_token(
        *,
        request_ip: str | None = None,
        user_agent: str | None = None,
        user: User | None = None,
    ) -> TelegramLoginTokenResult:
        token = secrets.token_urlsafe(24)
        login_token = TelegramLoginToken.objects.create(
            token=token,
            user=user,
            expires_at=timezone.now() + timedelta(seconds=TelegramAuthService._login_token_ttl_seconds()),
            requested_by_ip=request_ip,
            user_agent=TelegramAuthService._trim_user_agent(user_agent),
        )
        telegram_url = TelegramAuthProvider().build_deep_link(login_token=login_token.token)
        return TelegramLoginTokenResult(login_token=login_token, telegram_url=telegram_url)

    @staticmethod
    def confirm_login_token(
        *,
        token: str,
        telegram_id: int,
        chat_id: int | None = None,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
        photo_url: str = "",
        auth_date=None,
    ) -> TelegramLoginToken:
        login_token = TelegramAuthService._get_login_token(token=token)
        if login_token.is_expired or login_token.is_completed:
            raise ValidationError("Токен входа истёк. Вернитесь на сайт и начните вход заново.")

        identity = TelegramIdentity(
            telegram_id=telegram_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
            auth_date=auth_date,
        )
        with transaction.atomic():
            if login_token.user_id:
                user, account = TelegramAuthService._bind_account_to_user(user=login_token.user, identity=identity)
            else:
                user, account = TelegramAuthService._get_or_create_user(identity)

            login_token.user = user
            login_token.telegram_account = account
            login_token.confirmed_at = timezone.now()
            login_token.save(update_fields=["user", "telegram_account", "confirmed_at", "updated_at"])
        AuditLogService.log(
            action="user.telegram_login_confirmed",
            obj=user,
            metadata={"telegram_id": telegram_id, "token": login_token.token[:8]},
        )
        return login_token

    @staticmethod
    def get_login_status(*, token: str) -> TelegramLoginStatus:
        login_token = TelegramAuthService._get_login_token(token=token)
        telegram_url = TelegramAuthProvider().build_deep_link(login_token=login_token.token)

        if login_token.is_completed:
            status = "completed"
        elif login_token.is_expired:
            status = "expired"
        elif login_token.is_confirmed:
            status = "confirmed"
        else:
            status = "pending"

        account = login_token.telegram_account
        return TelegramLoginStatus(
            login_token=login_token,
            status=status,
            telegram_url=telegram_url,
            display_name=TelegramAuthService._build_display_name(account) if account else "",
            debug_code=TelegramAuthService._get_debug_code(login_token=login_token),
        )

    @staticmethod
    def issue_code(
        *,
        login_token: TelegramLoginToken | None = None,
        token: str | None = None,
        telegram_id: int | None = None,
        request_ip: str | None = None,
        user_agent: str | None = None,
        send_message: bool = True,
    ) -> TelegramCodeIssueResult:
        if login_token is None and token:
            login_token = TelegramAuthService._get_login_token(token=token)

        if login_token is not None:
            if login_token.is_expired or login_token.is_completed or not login_token.is_confirmed or not login_token.telegram_account:
                raise ValidationError("Telegram не подтвержден. Начните вход заново.")
            account = login_token.telegram_account
        elif telegram_id is not None:
            account = TelegramAccount.objects.select_related("user").filter(telegram_id=telegram_id).first()
            if not account:
                raise ValidationError("Сначала подтвердите Telegram на странице входа.")
        else:
            raise ValidationError("Не удалось определить Telegram-аккаунт.")

        now = timezone.now()
        TelegramAuthCode.objects.filter(
            telegram_account=account,
            used_at__isnull=True,
            expires_at__gt=now,
        ).update(used_at=now, updated_at=now)

        raw_code = f"{random.SystemRandom().randint(0, 999999):06d}"
        auth_code = TelegramAuthCode.objects.create(
            user=account.user,
            telegram_account=account,
            login_token=login_token,
            telegram_id=account.telegram_id,
            code_hash=make_password(raw_code),
            expires_at=now + timedelta(seconds=TelegramAuthService.CODE_TTL_SECONDS),
            max_attempts=TelegramAuthService.MAX_ATTEMPTS,
            ip_address=request_ip,
            user_agent=TelegramAuthService._trim_user_agent(user_agent),
        )

        TelegramAuthService._store_debug_code(code=raw_code, login_token=login_token, telegram_id=account.telegram_id)

        try:
            if send_message:
                TelegramAuthService._send_code_via_bot(account=account, code=raw_code)
        except ValidationError:
            auth_code.used_at = now
            auth_code.save(update_fields=["used_at", "updated_at"])
            raise

        if login_token is not None:
            login_token.code_sent_at = now
            login_token.save(update_fields=["code_sent_at", "updated_at"])

        AuditLogService.log(
            action="user.telegram_code_issued",
            obj=account.user,
            metadata={"telegram_id": account.telegram_id},
        )
        debug_code = raw_code if TelegramAuthService._is_debug_mode() else None
        return TelegramCodeIssueResult(auth_code=auth_code, raw_code=raw_code, debug_code=debug_code)

    @staticmethod
    def issue_code_for_pending_login(
        *,
        telegram_id: int,
        chat_id: int | None = None,
        request_ip: str | None = None,
        user_agent: str | None = None,
        send_message: bool = True,
    ) -> TelegramCodeIssueResult:
        account = TelegramAccount.objects.select_related("user").filter(telegram_id=telegram_id).first()
        if not account:
            raise ValidationError("Откройте страницу входа Sadaka и нажмите «Войти через Telegram».")

        if chat_id and account.chat_id != chat_id:
            account.chat_id = chat_id
            account.save(update_fields=["chat_id", "updated_at"])

        login_token = (
            TelegramLoginToken.objects.select_related("telegram_account", "user")
            .filter(
                telegram_account=account,
                confirmed_at__isnull=False,
                completed_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .order_by("-confirmed_at", "-created_at")
            .first()
        )
        if not login_token:
            raise ValidationError("Откройте страницу входа Sadaka и начните авторизацию заново.")

        return TelegramAuthService.issue_code(
            login_token=login_token,
            request_ip=request_ip,
            user_agent=user_agent,
            send_message=send_message,
        )

    @staticmethod
    def verify_code(*, token: str, code: str) -> tuple[User, dict[str, str]]:
        login_token = TelegramAuthService._get_login_token(token=token)
        if login_token.is_expired:
            raise ValidationError("Код истёк. Запросите новый.")
        if login_token.is_completed:
            raise ValidationError("Вход уже подтвержден. Начните новый сеанс.")
        if not login_token.is_confirmed or not login_token.user:
            raise ValidationError("Не удалось подтвердить Telegram. Попробуйте ещё раз.")

        auth_code = (
            TelegramAuthCode.objects.filter(
                login_token=login_token,
                used_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        if not auth_code or auth_code.is_expired:
            raise ValidationError("Код истёк. Запросите новый.")
        if auth_code.attempts >= auth_code.max_attempts:
            raise ValidationError("Код заблокирован. Запросите новый.")

        normalized_code = "".join(ch for ch in (code or "") if ch.isdigit())
        if len(normalized_code) != 6 or not check_password(normalized_code, auth_code.code_hash):
            auth_code.attempts += 1
            auth_code.save(update_fields=["attempts", "updated_at"])
            remaining_attempts = max(auth_code.max_attempts - auth_code.attempts, 0)
            AuditLogService.log(
                action="user.telegram_code_failed",
                obj=login_token.user,
                metadata={"telegram_id": auth_code.telegram_id, "remaining_attempts": remaining_attempts},
            )
            if remaining_attempts == 0:
                raise ValidationError("Код заблокирован. Запросите новый.")
            raise ValidationError(f"Код неверный. Осталось {remaining_attempts} попыток.")

        now = timezone.now()
        auth_code.used_at = now
        auth_code.save(update_fields=["used_at", "updated_at"])
        login_token.completed_at = now
        login_token.save(update_fields=["completed_at", "updated_at"])

        user = login_token.user
        UserService._touch_last_activity(user)
        AuditLogService.log(
            action="user.telegram_code_verified",
            obj=user,
            metadata={"telegram_id": auth_code.telegram_id},
        )
        return user, UserService.issue_tokens(user=user)
