from django.contrib import admin
from django.contrib import messages

from unfold.contrib.filters.admin import BooleanRadioFilter, ChoicesDropdownFilter, RelatedDropdownFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from apps.projects.models import Project
from apps.projects.services import ProjectService
from common.admin import ModelAdmin, MosqueScopedAdminMixin, admin_link_for


@admin.action(description="Одобрить выбранные проекты")
def approve_projects(modeladmin, request, queryset):
    updated = 0
    for project in queryset:
        ProjectService.approve(project=project, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Одобрено проектов: {updated}")


@admin.action(description="Отклонить выбранные проекты")
def reject_projects(modeladmin, request, queryset):
    updated = 0
    for project in queryset:
        ProjectService.reject(project=project, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Отклонено проектов: {updated}", level=messages.WARNING)


@admin.action(description="Заблокировать выбранные проекты")
def block_projects(modeladmin, request, queryset):
    updated = 0
    for project in queryset:
        ProjectService.block(project=project, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Заблокировано проектов: {updated}", level=messages.WARNING)


@admin.action(description="Пересчитать собранную сумму")
def recompute_projects(modeladmin, request, queryset):
    updated = 0
    for project in queryset:
        ProjectService.recompute_current_amount(project_id=project.id)
        updated += 1
    modeladmin.notify_action(request, f"Пересчитано проектов: {updated}")


@admin.register(Project)
class ProjectAdmin(MosqueScopedAdminMixin, ModelAdmin):
    actions = [approve_projects, reject_projects, block_projects, recompute_projects]
    actions_detail = ["approve_detail", "reject_detail", "block_detail", "recompute_detail"]
    autocomplete_fields = ("mosque",)
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"
    list_display = (
        "overview",
        "mosque_link",
        "status_badge",
        "progress_badge",
        "goal_amount",
        "current_amount",
        "blocked_badge",
    )
    list_filter = (
        ("status", ChoicesDropdownFilter),
        ("mosque", RelatedDropdownFilter),
        ("is_blocked", BooleanRadioFilter),
    )
    list_select_related = ("mosque", "created_by")
    readonly_fields = ("created_by", "current_amount", "published_at", "created_at", "updated_at", "deleted_at")
    search_fields = ("title", "description", "mosque__name")
    fieldsets = (
        ("Основные сведения", {"fields": ("mosque", "title", "slug", "cover_image", "description", "created_by")}),
        ("Статус и публикация", {"fields": ("status", "is_blocked", "published_at")}),
        ("Финансы и сроки", {"fields": ("goal_amount", "current_amount", "start_date", "end_date")}),
        ("Служебные поля", {"fields": ("is_deleted", "deleted_at", "created_at", "updated_at")}),
    )

    restrict_user_fields = ("created_by",)

    def _belongs_to_managed_mosque(self, request, obj):
        return obj.mosque.memberships.filter(user=request.user).exists()

    @display(header=True, description="Проект")
    def overview(self, obj):
        return [obj.title, obj.published_at.strftime("%d.%m.%Y %H:%M") if obj.published_at else "Не опубликован", "PR"]

    @display(description="Мечеть")
    def mosque_link(self, obj):
        return admin_link_for(obj.mosque, label=obj.mosque.name)

    @display(
        description="Статус",
        ordering="status",
        label={
            Project.Status.DRAFT: "info",
            Project.Status.PENDING: "warning",
            Project.Status.APPROVED: "success",
            Project.Status.REJECTED: "danger",
            Project.Status.ACTIVE: "success",
            Project.Status.COMPLETED: "info",
            Project.Status.ARCHIVED: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Прогресс", ordering="current_amount", label=True)
    def progress_badge(self, obj):
        return f"{obj.progress}%", f"{obj.current_amount} из {obj.goal_amount}"

    @display(description="Блокировка", label={"Заблокирован": "danger", "Активен": "success"})
    def blocked_badge(self, obj):
        return "Заблокирован" if obj.is_blocked else "Активен"

    @action(description="Одобрить", permissions=["approve_detail"], icon="check_circle", variant=ActionVariant.SUCCESS)
    def approve_detail(self, request, object_id):
        project = self.get_action_object(request, object_id)
        ProjectService.approve(project=project, actor=request.user)
        self.notify_action(request, f"Проект «{project.title}» одобрен.")
        return self.redirect_to_change(project)

    def has_approve_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)

    @action(description="Отклонить", permissions=["reject_detail"], icon="cancel", variant=ActionVariant.DANGER)
    def reject_detail(self, request, object_id):
        project = self.get_action_object(request, object_id)
        ProjectService.reject(project=project, actor=request.user)
        self.notify_action(request, f"Проект «{project.title}» отклонен.", level=messages.WARNING)
        return self.redirect_to_change(project)

    def has_reject_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)

    @action(description="Заблокировать", permissions=["block_detail"], icon="block", variant=ActionVariant.WARNING)
    def block_detail(self, request, object_id):
        project = self.get_action_object(request, object_id)
        ProjectService.block(project=project, actor=request.user)
        self.notify_action(request, f"Проект «{project.title}» заблокирован.", level=messages.WARNING)
        return self.redirect_to_change(project)

    def has_block_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)

    @action(description="Пересчитать сумму", permissions=["recompute_detail"], icon="sync", variant=ActionVariant.INFO)
    def recompute_detail(self, request, object_id):
        project = self.get_action_object(request, object_id)
        ProjectService.recompute_current_amount(project_id=project.id)
        self.notify_action(request, f"Сумма проекта «{project.title}» пересчитана.")
        return self.redirect_to_change(project)

    def has_recompute_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)
