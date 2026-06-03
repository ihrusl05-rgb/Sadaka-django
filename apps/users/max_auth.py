from __future__ import annotations

import json
import logging
import os
import random
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.platform.services import AuditLogService
from apps.users.auth_providers.max import MaxAuthProvider
from apps.users.models import MaxAccount, MaxAuthCode, MaxLoginToken, User
from apps.users.services import UserService

logger = logging.getLogger(__name__)


@dataclass
class MaxLoginTokenResult:
    login_token: MaxLoginToken
    max_url: str


@dataclass
class MaxLoginStatus:
    login_token: MaxLoginToken
    status: str
    max_url: str
    display_name: str = ""
    debug_code: str | None = None


@dataclass
class MaxCodeIssueResult:
    auth_code: MaxAuthCode
    raw_code: str
    debug_code: str | None = None


@dataclass
class MaxIdentity:
    max_user_id: int
    chat_id: int | None = None
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    photo_url: str = ""
    auth_date: datetime | None = None


class MaxBotClient:
    @staticmethod
    def _base_url() -> str:
        return (getattr(settings, "MAX_BOT_API_BASE_URL", "") or "").strip().rstrip("/")

    @staticmethod
    def _bot_token() -> str:
        return (getattr(settings, "MAX_AUTH_BOT_TOKEN", "") or "").strip()

    @classmethod
    def send_text(cls, *, chat_id: int | None = None, user_id: int | None = None, text: str) -> None:
        token = cls._bot_token()
        if not token:
            raise ValidationError("MAX_AUTH_BOT_TOKEN не настроен.")
        if not chat_id and not user_id:
            raise ValidationError("Не указан chat_id или user_id для отправки сообщения в MAX.")

        params: dict[str, int] = {}
        if chat_id:
            params["chat_id"] = chat_id
        else:
            params["user_id"] = user_id or 0

        payload = json.dumps({"text": text}).encode("utf-8")
        request = Request(
            f"{cls._base_url()}/messages?{urlencode(params)}",
            data=payload,
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.exception("Failed to send MAX auth message", extra={"chat_id": chat_id, "user_id": user_id})
            raise ValidationError("Не удалось отправить код в MAX. Попробуйте еще раз.") from exc


class MaxAuthService:
    CODE_TTL_SECONDS = 5 * 60
    MAX_ATTEMPTS = 5

    @staticmethod
    def _login_token_ttl_seconds() -> int:
        return int(getattr(settings, "MAX_LOGIN_TOKEN_TTL_SECONDS", 300))

    @staticmethod
    def _is_debug_mode() -> bool:
        return bool(settings.DEBUG or os.environ.get("PYTEST_CURRENT_TEST"))

    @staticmethod
    def _trim_user_agent(user_agent: str | None) -> str:
        return (user_agent or "").strip()[:255]

    @staticmethod
    def _build_placeholder_email(max_user_id: int) -> str:
        return f"max_{max_user_id}@{User.MAX_AUTH_EMAIL_DOMAIN}"

    @staticmethod
    def _debug_cache_key(*, token: str | None = None, max_user_id: int | None = None) -> str:
        if token:
            return f"auth:max:debug:token:{token}"
        return f"auth:max:debug:user:{max_user_id}"

    @staticmethod
    def _store_debug_code(*, code: str, login_token: MaxLoginToken | None, max_user_id: int) -> None:
        if not MaxAuthService._is_debug_mode():
            return
        timeout = MaxAuthService.CODE_TTL_SECONDS
        if login_token is not None:
            cache.set(MaxAuthService._debug_cache_key(token=login_token.token), code, timeout=timeout)
        cache.set(MaxAuthService._debug_cache_key(max_user_id=max_user_id), code, timeout=timeout)

    @staticmethod
    def _get_debug_code(*, login_token: MaxLoginToken | None = None, max_user_id: int | None = None) -> str | None:
        if not MaxAuthService._is_debug_mode():
            return None
        if login_token is not None:
            return cache.get(MaxAuthService._debug_cache_key(token=login_token.token))
        if max_user_id is not None:
            return cache.get(MaxAuthService._debug_cache_key(max_user_id=max_user_id))
        return None

    @staticmethod
    def _build_display_name(account: MaxAccount) -> str:
        if account.username:
            return f"@{account.username}"
        full_name = User.build_full_name(last_name=account.last_name, first_name=account.first_name).strip()
        if full_name:
            return full_name
        return str(account.max_user_id)

    @staticmethod
    def _can_transfer_existing_account(*, existing_owner: User) -> bool:
        if User.is_placeholder_email(existing_owner.email):
            return True
        return not existing_owner.has_usable_password()

    @staticmethod
    def build_login_code_message(*, code: str) -> str:
        return "\n".join(
            [
                "Код входа в Sadaka",
                "",
                f"Ваш код: {code}",
                "",
                "Код действует 5 минут.",
                "Если это были не вы, просто проигнорируйте сообщение.",
            ]
        )

    @staticmethod
    def _send_code_via_bot(*, account: MaxAccount, code: str) -> None:
        if not account.chat_id:
            raise ValidationError("MAX-чат не привязан. Откройте бота по ссылке со страницы входа.")
        if not getattr(settings, "MAX_AUTH_BOT_TOKEN", "").strip():
            if MaxAuthService._is_debug_mode():
                return
            raise ValidationError("MAX_AUTH_BOT_TOKEN не настроен.")
        MaxBotClient.send_text(chat_id=account.chat_id, user_id=account.max_user_id, text=MaxAuthService.build_login_code_message(code=code))

    @staticmethod
    def _get_login_token(*, token: str) -> MaxLoginToken:
        login_token = MaxLoginToken.objects.select_related("user", "max_account", "max_account__user").filter(token=token).first()
        if not login_token:
            raise ValidationError("Не удалось подтвердить MAX. Попробуйте ещё раз.")
        return login_token

    @staticmethod
    def _get_or_create_user(identity: MaxIdentity) -> tuple[User, MaxAccount]:
        account = MaxAccount.objects.select_related("user").filter(max_user_id=identity.max_user_id).first()

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
            email=MaxAuthService._build_placeholder_email(identity.max_user_id),
            password=None,
            first_name=(identity.first_name or "").strip(),
            last_name=(identity.last_name or "").strip(),
            full_name=User.build_full_name(
                last_name=(identity.last_name or "").strip(),
                first_name=(identity.first_name or "").strip(),
            ),
        )
        account = MaxAccount.objects.create(
            user=user,
            max_user_id=identity.max_user_id,
            chat_id=identity.chat_id,
            username=(identity.username or "").strip(),
            first_name=(identity.first_name or "").strip(),
            last_name=(identity.last_name or "").strip(),
            photo_url=(identity.photo_url or "").strip(),
            auth_date=identity.auth_date,
            linked_at=timezone.now(),
        )
        AuditLogService.log(
            action="user.max_linked",
            obj=user,
            metadata={"max_user_id": identity.max_user_id, "username": account.username},
        )
        NotificationService.notify_platform_admins(
            title="Новый пользователь зарегистрирован",
            message=f"Пользователь {MaxAuthService._build_display_name(account)} вошел через MAX.",
            event=Notification.Event.NEW_USER_REGISTERED,
            notification_type=Notification.NotificationType.INFO,
            link="/admin/users/user/",
            payload={"user_id": user.id, "max_user_id": identity.max_user_id},
        )
        return user, account

    @staticmethod
    def _bind_account_to_user(*, user: User, identity: MaxIdentity) -> tuple[User, MaxAccount]:
        existing_account = MaxAccount.objects.select_related("user").filter(max_user_id=identity.max_user_id).first()
        current_account = MaxAccount.objects.select_related("user").filter(user=user).first()
        transferred_account = False

        if current_account and current_account.max_user_id != identity.max_user_id:
            raise ValidationError("К вашему профилю уже привязан другой MAX-аккаунт.")

        if existing_account and existing_account.user_id != user.id:
            existing_owner = existing_account.user
            if not MaxAuthService._can_transfer_existing_account(existing_owner=existing_owner):
                raise ValidationError("Этот MAX уже привязан к другому аккаунту Sadaka.")
            existing_account.user = user
            existing_account.linked_at = timezone.now()
            transferred_account = True

        account = existing_account or current_account
        if account is None:
            account = MaxAccount(user=user, max_user_id=identity.max_user_id, linked_at=timezone.now())

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
            action="user.max_linked",
            obj=user,
            metadata={"max_user_id": identity.max_user_id, "username": account.username},
        )
        return user, account

    @staticmethod
    def create_login_token(
        *,
        request_ip: str | None = None,
        user_agent: str | None = None,
        user: User | None = None,
    ) -> MaxLoginTokenResult:
        token = secrets.token_urlsafe(24)
        login_token = MaxLoginToken.objects.create(
            token=token,
            user=user,
            expires_at=timezone.now() + timedelta(seconds=MaxAuthService._login_token_ttl_seconds()),
            requested_by_ip=request_ip,
            user_agent=MaxAuthService._trim_user_agent(user_agent),
        )
        max_url = MaxAuthProvider().build_deep_link(login_token=login_token.token)
        return MaxLoginTokenResult(login_token=login_token, max_url=max_url)

    @staticmethod
    def confirm_login_token(
        *,
        token: str,
        max_user_id: int,
        chat_id: int | None = None,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
        photo_url: str = "",
        auth_date: datetime | None = None,
    ) -> MaxLoginToken:
        login_token = MaxAuthService._get_login_token(token=token)
        if login_token.is_expired or login_token.is_completed:
            raise ValidationError("Токен входа истёк. Вернитесь на сайт и начните вход заново.")

        identity = MaxIdentity(
            max_user_id=max_user_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
            auth_date=auth_date,
        )
        with transaction.atomic():
            if login_token.user_id:
                user, account = MaxAuthService._bind_account_to_user(user=login_token.user, identity=identity)
            else:
                user, account = MaxAuthService._get_or_create_user(identity)

            login_token.user = user
            login_token.max_account = account
            login_token.confirmed_at = timezone.now()
            login_token.save(update_fields=["user", "max_account", "confirmed_at", "updated_at"])
        AuditLogService.log(
            action="user.max_login_confirmed",
            obj=user,
            metadata={"max_user_id": max_user_id, "token": login_token.token[:8]},
        )
        return login_token

    @staticmethod
    def get_login_status(*, token: str) -> MaxLoginStatus:
        login_token = MaxAuthService._get_login_token(token=token)
        max_url = MaxAuthProvider().build_deep_link(login_token=login_token.token)

        if login_token.is_completed:
            status = "completed"
        elif login_token.is_expired:
            status = "expired"
        elif login_token.is_confirmed:
            status = "confirmed"
        else:
            status = "pending"

        account = login_token.max_account
        return MaxLoginStatus(
            login_token=login_token,
            status=status,
            max_url=max_url,
            display_name=MaxAuthService._build_display_name(account) if account else "",
            debug_code=MaxAuthService._get_debug_code(login_token=login_token),
        )

    @staticmethod
    def issue_code(
        *,
        login_token: MaxLoginToken | None = None,
        token: str | None = None,
        max_user_id: int | None = None,
        request_ip: str | None = None,
        user_agent: str | None = None,
        send_message: bool = True,
    ) -> MaxCodeIssueResult:
        if login_token is None and token:
            login_token = MaxAuthService._get_login_token(token=token)

        if login_token is not None:
            if login_token.is_expired or login_token.is_completed or not login_token.is_confirmed or not login_token.max_account:
                raise ValidationError("MAX не подтвержден. Начните вход заново.")
            account = login_token.max_account
        elif max_user_id is not None:
            account = MaxAccount.objects.select_related("user").filter(max_user_id=max_user_id).first()
            if not account:
                raise ValidationError("Сначала подтвердите MAX на странице входа.")
        else:
            raise ValidationError("Не удалось определить MAX-аккаунт.")

        now = timezone.now()
        MaxAuthCode.objects.filter(max_account=account, used_at__isnull=True, expires_at__gt=now).update(used_at=now, updated_at=now)

        raw_code = f"{random.SystemRandom().randint(0, 999999):06d}"
        auth_code = MaxAuthCode.objects.create(
            user=account.user,
            max_account=account,
            login_token=login_token,
            max_user_id=account.max_user_id,
            code_hash=make_password(raw_code),
            expires_at=now + timedelta(seconds=MaxAuthService.CODE_TTL_SECONDS),
            max_attempts=MaxAuthService.MAX_ATTEMPTS,
            ip_address=request_ip,
            user_agent=MaxAuthService._trim_user_agent(user_agent),
        )

        MaxAuthService._store_debug_code(code=raw_code, login_token=login_token, max_user_id=account.max_user_id)

        try:
            if send_message:
                MaxAuthService._send_code_via_bot(account=account, code=raw_code)
        except ValidationError:
            auth_code.used_at = now
            auth_code.save(update_fields=["used_at", "updated_at"])
            raise

        if login_token is not None:
            login_token.code_sent_at = now
            login_token.save(update_fields=["code_sent_at", "updated_at"])

        AuditLogService.log(action="user.max_code_issued", obj=account.user, metadata={"max_user_id": account.max_user_id})
        debug_code = raw_code if MaxAuthService._is_debug_mode() else None
        return MaxCodeIssueResult(auth_code=auth_code, raw_code=raw_code, debug_code=debug_code)

    @staticmethod
    def issue_code_for_pending_login(
        *,
        max_user_id: int,
        chat_id: int | None = None,
        request_ip: str | None = None,
        user_agent: str | None = None,
        send_message: bool = True,
    ) -> MaxCodeIssueResult:
        account = MaxAccount.objects.select_related("user").filter(max_user_id=max_user_id).first()
        if not account:
            raise ValidationError("Откройте страницу входа Sadaka и нажмите «Войти через MAX».")

        if chat_id and account.chat_id != chat_id:
            account.chat_id = chat_id
            account.save(update_fields=["chat_id", "updated_at"])

        login_token = (
            MaxLoginToken.objects.select_related("max_account", "user")
            .filter(
                max_account=account,
                confirmed_at__isnull=False,
                completed_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .order_by("-confirmed_at", "-created_at")
            .first()
        )
        if not login_token:
            raise ValidationError("Откройте страницу входа Sadaka и начните авторизацию заново.")

        return MaxAuthService.issue_code(
            login_token=login_token,
            request_ip=request_ip,
            user_agent=user_agent,
            send_message=send_message,
        )

    @staticmethod
    def verify_code(*, token: str, code: str) -> tuple[User, dict[str, str]]:
        login_token = MaxAuthService._get_login_token(token=token)
        if login_token.is_expired:
            raise ValidationError("Код истёк. Запросите новый.")
        if login_token.is_completed:
            raise ValidationError("Вход уже подтвержден. Начните новый сеанс.")
        if not login_token.is_confirmed or not login_token.user:
            raise ValidationError("Не удалось подтвердить MAX. Попробуйте ещё раз.")

        auth_code = MaxAuthCode.objects.filter(login_token=login_token, used_at__isnull=True).order_by("-created_at").first()
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
                action="user.max_code_failed",
                obj=login_token.user,
                metadata={"max_user_id": auth_code.max_user_id, "remaining_attempts": remaining_attempts},
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
        AuditLogService.log(action="user.max_code_verified", obj=user, metadata={"max_user_id": auth_code.max_user_id})
        return user, UserService.issue_tokens(user=user)
