from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.platform.services import AuditLogService
from apps.projects.models import Project


class ProjectService:
    @staticmethod
    def create_project(*, actor, **payload) -> Project:
        project = Project.objects.create(created_by=actor, **payload)
        AuditLogService.log(action="project.created", obj=project, actor=actor)
        NotificationService.notify_platform_admins(
            title="Новый проект на модерации",
            message=f"Проект «{project.title}» для мечети «{project.mosque.name}» отправлен на проверку.",
            event=Notification.Event.PROJECT_SUBMITTED,
            notification_type=Notification.NotificationType.INFO,
            link="/admin/projects/project/",
            payload={"project_id": project.id, "mosque_id": project.mosque_id},
            telegram=True,
        )
        NotificationService.notify_mosque_admins(
            mosque=project.mosque,
            title="Проект создан",
            message=f"Проект «{project.title}» создан и ожидает модерации.",
            event=Notification.Event.MOSQUE_PROJECT_CREATED,
            notification_type=Notification.NotificationType.INFO,
            link="/profile/",
            payload={"project_id": project.id},
        )
        return project

    @staticmethod
    def update_project(*, project: Project, actor, **payload) -> Project:
        for field, value in payload.items():
            setattr(project, field, value)
        project.save()
        AuditLogService.log(action="project.updated", obj=project, actor=actor)
        return project

    @staticmethod
    def approve(*, project: Project, actor) -> Project:
        project.status = Project.Status.APPROVED
        project.published_at = project.published_at or timezone.now()
        project.save(update_fields=["status", "published_at", "updated_at"])
        AuditLogService.log(action="project.approved", obj=project, actor=actor)
        if project.created_by_id:
            NotificationService.notify_user(
                project.created_by,
                title="Проект одобрен",
                message=f"Проект «{project.title}» прошел модерацию и опубликован.",
                event=Notification.Event.PROJECT_APPROVED,
                notification_type=Notification.NotificationType.SUCCESS,
                link=f"/mosques/{project.mosque.slug}/",
                payload={"project_id": project.id},
                telegram=True,
            )
        NotificationService.notify_mosque_admins(
            mosque=project.mosque,
            title="Проект одобрен",
            message=f"Проект «{project.title}» одобрен и доступен для пожертвований.",
            event=Notification.Event.MOSQUE_PROJECT_APPROVED,
            notification_type=Notification.NotificationType.SUCCESS,
            link=f"/mosques/{project.mosque.slug}/",
            payload={"project_id": project.id},
        )
        return project

    @staticmethod
    def reject(*, project: Project, actor) -> Project:
        project.status = Project.Status.REJECTED
        project.save(update_fields=["status", "updated_at"])
        AuditLogService.log(action="project.rejected", obj=project, actor=actor)
        if project.created_by_id:
            NotificationService.notify_user(
                project.created_by,
                title="Проект отклонен",
                message=f"Проект «{project.title}» пока не прошел модерацию. Проверьте описание и данные проекта.",
                event=Notification.Event.PROJECT_REJECTED,
                notification_type=Notification.NotificationType.WARNING,
                link="/profile/",
                payload={"project_id": project.id},
                telegram=True,
            )
        NotificationService.notify_mosque_admins(
            mosque=project.mosque,
            title="Проект отклонен",
            message=f"Проект «{project.title}» не прошел модерацию.",
            event=Notification.Event.MOSQUE_PROJECT_REJECTED,
            notification_type=Notification.NotificationType.WARNING,
            link="/profile/",
            payload={"project_id": project.id},
        )
        return project

    @staticmethod
    def block(*, project: Project, actor) -> Project:
        project.is_blocked = True
        project.save(update_fields=["is_blocked", "updated_at"])
        AuditLogService.log(action="project.blocked", obj=project, actor=actor)
        return project

    @staticmethod
    def recompute_current_amount(*, project_id: int) -> Decimal:
        Donation = Project._meta.apps.get_model("donations", "Donation")
        project = Project.objects.get(id=project_id)
        total = (
            Donation.objects.filter(project_id=project.id, status=Donation.Status.SUCCEEDED).aggregate(
                total=Sum("net_amount")
            )["total"]
            or Decimal("0.00")
        )
        project.current_amount = total
        project.save(update_fields=["current_amount", "updated_at"])
        return total

    @staticmethod
    def recompute_mosque_aggregates(*, mosque_id: int):
        for project_id in Project.objects.filter(mosque_id=mosque_id).values_list("id", flat=True):
            ProjectService.recompute_current_amount(project_id=project_id)
