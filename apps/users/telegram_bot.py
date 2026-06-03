from __future__ import annotations

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import Notification
from apps.platform.models import MosqueSiteRequest
from apps.projects.models import Project
from apps.users.models import TelegramAccount, User


class SadakaTelegramBotService:
    @staticmethod
    def get_account(*, telegram_id: int) -> TelegramAccount | None:
        return TelegramAccount.objects.select_related("user").filter(telegram_id=telegram_id).first()

    @staticmethod
    def get_user(*, telegram_id: int) -> User | None:
        account = SadakaTelegramBotService.get_account(telegram_id=telegram_id)
        return account.user if account else None

    @staticmethod
    def sync_chat_context(
        *,
        telegram_id: int,
        chat_id: int | None = None,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
    ) -> TelegramAccount | None:
        account = SadakaTelegramBotService.get_account(telegram_id=telegram_id)
        if not account:
            return None

        update_fields = ["updated_at"]
        if chat_id and account.chat_id != chat_id:
            account.chat_id = chat_id
            update_fields.append("chat_id")
        for field_name, value in (
            ("username", username),
            ("first_name", first_name),
            ("last_name", last_name),
        ):
            value = (value or "").strip()
            if value and getattr(account, field_name) != value:
                setattr(account, field_name, value)
                update_fields.append(field_name)
        if len(update_fields) > 1:
            account.save(update_fields=update_fields)
        return account

    @staticmethod
    def is_linked(*, telegram_id: int) -> bool:
        return SadakaTelegramBotService.get_account(telegram_id=telegram_id) is not None

    @staticmethod
    def issue_login_code_for_linked_account(
        *,
        telegram_id: int,
        chat_id: int | None = None,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
    ) -> bool:
        account = SadakaTelegramBotService.sync_chat_context(
            telegram_id=telegram_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        if not account:
            return False
        from apps.users.telegram_auth import TelegramAuthService

        TelegramAuthService.issue_code_for_pending_login(
            telegram_id=telegram_id,
            chat_id=chat_id,
            user_agent="sadaka-bot",
        )
        return True

    @staticmethod
    def build_link_status(*, telegram_id: int) -> dict:
        account = SadakaTelegramBotService.get_account(telegram_id=telegram_id)
        if not account:
            return {
                "is_linked": False,
                "display_name": "",
                "linked_at": None,
                "user": None,
            }
        display_name = f"@{account.username}" if account.username else "Аккаунт Telegram подключён"
        return {
            "is_linked": True,
            "display_name": display_name,
            "linked_at": account.linked_at,
            "user": account.user,
        }

    @staticmethod
    def build_status_payload(*, telegram_id: int) -> dict:
        account = SadakaTelegramBotService.get_account(telegram_id=telegram_id)
        if not account:
            return {
                "is_linked": False,
                "email": "",
                "notifications_total": 0,
                "requests_total": 0,
                "projects_total": 0,
                "managed_mosques_total": 0,
            }

        user = account.user
        requests_total = 0
        if user.phone:
            requests_total = MosqueSiteRequest.objects.filter(phone=user.phone).count()

        projects_qs = SadakaTelegramBotService._projects_queryset(user=user)
        managed_mosques_total = user.managed_mosques.count() if hasattr(user, "managed_mosques") else 0
        return {
            "is_linked": True,
            "display_name": f"@{account.username}" if account.username else "Telegram привязан",
            "email": user.profile_email,
            "notifications_total": Notification.objects.filter(user=user).count(),
            "notifications_unread": Notification.objects.filter(user=user, is_read=False).count(),
            "requests_total": requests_total,
            "projects_total": projects_qs.count(),
            "managed_mosques_total": managed_mosques_total,
            "linked_at": account.linked_at,
            "user": user,
        }

    @staticmethod
    def recent_notifications(*, telegram_id: int, limit: int = 5):
        user = SadakaTelegramBotService.get_user(telegram_id=telegram_id)
        if not user:
            return Notification.objects.none()
        return Notification.objects.filter(user=user).order_by("-created_at")[:limit]

    @staticmethod
    def recent_requests(*, telegram_id: int, limit: int = 5):
        user = SadakaTelegramBotService.get_user(telegram_id=telegram_id)
        if not user or not user.phone:
            return MosqueSiteRequest.objects.none()
        return MosqueSiteRequest.objects.filter(phone=user.phone).order_by("-created_at")[:limit]

    @staticmethod
    def _projects_queryset(*, user: User):
        managed_mosque_ids = list(user.managed_mosques.values_list("id", flat=True)) if hasattr(user, "managed_mosques") else []
        return Project.objects.filter(Q(created_by=user) | Q(mosque_id__in=managed_mosque_ids)).select_related("mosque").distinct().order_by("-updated_at", "-created_at")

    @staticmethod
    def recent_projects(*, telegram_id: int, limit: int = 5):
        user = SadakaTelegramBotService.get_user(telegram_id=telegram_id)
        if not user:
            return Project.objects.none()
        return SadakaTelegramBotService._projects_queryset(user=user)[:limit]

    @staticmethod
    def resolve_user_for_site_request(*, request: MosqueSiteRequest) -> User | None:
        phone = (request.phone or "").strip()
        if not phone:
            return None
        return User.objects.filter(phone=phone, is_deleted=False).first()

    @staticmethod
    def format_currency(value: Decimal) -> str:
        return f"{value:,.0f}".replace(",", " ")

    @staticmethod
    def format_datetime(value) -> str:
        if not value:
            return "—"
        return timezone.localtime(value).strftime("%d.%m.%Y %H:%M")
