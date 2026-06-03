from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.platform.models import AuditLog, MosqueSiteRequest, PlatformSettings
from apps.users.telegram_bot import SadakaTelegramBotService
from common.utils.context import get_current_user


class AuditLogService:
    @staticmethod
    def log(*, action: str, obj=None, metadata: dict | None = None, actor=None) -> AuditLog:
        actor = actor if actor is not None else get_current_user()
        content_type = None
        object_id = ""
        model_label = ""
        if obj is not None:
            content_type = ContentType.objects.get_for_model(obj.__class__)
            object_id = str(obj.pk)
            model_label = content_type.model
        return AuditLog.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            content_type=content_type,
            object_id=object_id,
            model_label=model_label,
            metadata=metadata or {},
        )


class PlatformSettingsService:
    @staticmethod
    def get_settings() -> PlatformSettings:
        settings_obj, _ = PlatformSettings.objects.get_or_create(
            pk=1, defaults={"support_email": "support@sadaka.local"}
        )
        return settings_obj


class MosqueSiteRequestService:
    STATUS_LABELS = {
        MosqueSiteRequest.Status.NEW: "🆕 Новая",
        MosqueSiteRequest.Status.IN_PROGRESS: "📞 На связи",
        MosqueSiteRequest.Status.APPROVED: "✅ Обработана",
        MosqueSiteRequest.Status.REJECTED: "⛔ Не используется",
    }

    @staticmethod
    def create_help_request(*, full_name: str, mosque_name: str, region: str, phone: str) -> MosqueSiteRequest:
        request = MosqueSiteRequest.objects.create(
            request_type=MosqueSiteRequest.RequestType.HELP_FORM,
            full_name=full_name,
            mosque_name=mosque_name,
            region=region,
            phone=phone,
            source="help_page",
        )
        AuditLogService.log(action="mosque_request.created", obj=request, metadata={"request_type": request.request_type})
        return request

    @staticmethod
    def create_widget_request(*, mosque_name: str, city: str, applicant_name: str, phone: str, comment: str) -> MosqueSiteRequest:
        request = MosqueSiteRequest.objects.create(
            request_type=MosqueSiteRequest.RequestType.WIDGET_FORM,
            full_name=applicant_name,
            mosque_name=mosque_name,
            city=city,
            phone=phone,
            comment=comment,
            source="site_widget",
        )
        AuditLogService.log(action="mosque_request.created", obj=request, metadata={"request_type": request.request_type})
        return request

    @staticmethod
    def get_request(*, request_id: int) -> MosqueSiteRequest:
        return MosqueSiteRequest.objects.get(pk=request_id)

    @staticmethod
    def serialize(request: MosqueSiteRequest) -> dict:
        reviewer = request.reviewed_by_username.strip()
        if reviewer and not reviewer.startswith("@"):
            reviewer = f"@{reviewer}"
        return {
            "id": request.id,
            "request_type": request.request_type,
            "request_type_label": request.get_request_type_display(),
            "status": request.status,
            "status_label": MosqueSiteRequestService.STATUS_LABELS.get(request.status, request.get_status_display()),
            "full_name": request.full_name,
            "mosque_name": request.mosque_name,
            "region": request.region,
            "city": request.city,
            "phone": request.phone,
            "comment": request.comment,
            "source": request.source,
            "created_at": request.created_at,
            "reviewed_at": request.reviewed_at,
            "reviewed_by_telegram_id": request.reviewed_by_telegram_id,
            "reviewed_by_username": reviewer,
        }

    @staticmethod
    def get_snapshot(*, request_id: int) -> dict:
        return MosqueSiteRequestService.serialize(MosqueSiteRequestService.get_request(request_id=request_id))

    @staticmethod
    def set_status(
        *,
        request_id: int,
        status: str,
        admin_telegram_id: int | None = None,
        admin_username: str = "",
    ) -> dict:
        if status not in MosqueSiteRequest.Status.values:
            raise ValidationError("Недопустимый статус заявки.")

        request = MosqueSiteRequestService.get_request(request_id=request_id)
        update_fields = ["status", "updated_at"]
        request.status = status

        if status == MosqueSiteRequest.Status.NEW:
            request.reviewed_by_telegram_id = None
            request.reviewed_by_username = ""
            request.reviewed_at = None
            update_fields.extend(["reviewed_by_telegram_id", "reviewed_by_username", "reviewed_at"])
        else:
            request.reviewed_by_telegram_id = admin_telegram_id
            request.reviewed_by_username = (admin_username or "").strip()
            request.reviewed_at = timezone.now()
            update_fields.extend(["reviewed_by_telegram_id", "reviewed_by_username", "reviewed_at"])

        request.save(update_fields=update_fields)
        AuditLogService.log(
            action=f"mosque_request.{status}",
            obj=request,
            metadata={"admin_telegram_id": admin_telegram_id, "admin_username": admin_username},
        )
        related_user = SadakaTelegramBotService.resolve_user_for_site_request(request=request)
        if related_user:
            from apps.notifications.models import Notification
            from apps.notifications.services import NotificationService

            event_map = {
                MosqueSiteRequest.Status.NEW: Notification.Event.MOSQUE_REQUEST_SUBMITTED,
                MosqueSiteRequest.Status.IN_PROGRESS: Notification.Event.MOSQUE_REQUEST_CREATED,
                MosqueSiteRequest.Status.APPROVED: Notification.Event.MOSQUE_REQUEST_APPROVED,
                MosqueSiteRequest.Status.REJECTED: Notification.Event.MOSQUE_REQUEST_REJECTED,
            }
            title_map = {
                MosqueSiteRequest.Status.NEW: "Заявка на мечеть зарегистрирована",
                MosqueSiteRequest.Status.IN_PROGRESS: "По заявке на мечеть уже связываются",
                MosqueSiteRequest.Status.APPROVED: "Заявка на мечеть обработана",
                MosqueSiteRequest.Status.REJECTED: "Статус заявки обновлён",
            }
            message_map = {
                MosqueSiteRequest.Status.NEW: f"Заявка по мечети «{request.mosque_name}» зарегистрирована. С вами свяжутся после обработки.",
                MosqueSiteRequest.Status.IN_PROGRESS: f"По заявке по мечети «{request.mosque_name}» уже связываются.",
                MosqueSiteRequest.Status.APPROVED: f"Заявка по мечети «{request.mosque_name}» обработана.",
                MosqueSiteRequest.Status.REJECTED: f"Заявка по мечети «{request.mosque_name}» обновлена. Если нужно, уточните детали через поддержку.",
            }
            NotificationService.notify_user(
                related_user,
                title=title_map[status],
                message=message_map[status],
                event=event_map[status],
                notification_type=Notification.NotificationType.SUCCESS
                if status == MosqueSiteRequest.Status.APPROVED
                else Notification.NotificationType.INFO,
                link="/profile/notifications/",
                payload={"mosque_site_request_id": request.id},
                telegram=True,
            )
        return MosqueSiteRequestService.serialize(request)
