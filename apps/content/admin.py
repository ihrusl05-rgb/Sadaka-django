from django.contrib import admin
from django.contrib import messages

from unfold.contrib.filters.admin import BooleanRadioFilter, ChoicesDropdownFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from apps.content.models import ContentItem
from apps.content.services import ContentService
from common.admin import ModelAdmin, MosqueScopedAdminMixin


@admin.action(description="Одобрить выбранный контент")
def approve_content(modeladmin, request, queryset):
    updated = 0
    for item in queryset:
        ContentService.approve(item=item, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Одобрено материалов: {updated}")


@admin.action(description="Отклонить выбранный контент")
def reject_content(modeladmin, request, queryset):
    updated = 0
    for item in queryset:
        ContentService.reject(item=item, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Отклонено материалов: {updated}", level=messages.WARNING)


@admin.register(ContentItem)
class ContentItemAdmin(MosqueScopedAdminMixin, ModelAdmin):
    actions = [approve_content, reject_content]
    actions_detail = ["approve_detail", "reject_detail"]
    autocomplete_fields = ("mosque",)
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"
    list_display = ("overview", "scope_badge", "type", "moderation_badge", "published_badge", "blocked_badge")
    list_filter = (
        ("scope", ChoicesDropdownFilter),
        ("type", ChoicesDropdownFilter),
        ("moderation_status", ChoicesDropdownFilter),
        ("is_published", BooleanRadioFilter),
        ("is_blocked", BooleanRadioFilter),
    )
    list_select_related = ("mosque", "author")
    readonly_fields = ("author", "published_at", "created_at", "updated_at", "deleted_at")
    search_fields = ("title", "body")
    fieldsets = (
        ("Основные сведения", {"fields": ("title", "slug", "type", "scope", "mosque", "author")}),
        ("Содержимое", {"fields": ("body",)}),
        ("Публикация и модерация", {"fields": ("moderation_status", "is_published", "published_at", "is_blocked")}),
        ("Служебные поля", {"fields": ("is_deleted", "deleted_at", "created_at", "updated_at")}),
    )

    restrict_user_fields = ("author",)

    def _belongs_to_managed_mosque(self, request, obj):
        return bool(obj.mosque_id and obj.mosque.memberships.filter(user=request.user).exists())

    @display(header=True, description="Материал")
    def overview(self, obj):
        subtitle = obj.mosque.name if obj.mosque_id else "Платформенный контент"
        return [obj.title, subtitle, "CT"]

    @display(
        description="Область",
        ordering="scope",
        label={ContentItem.Scope.PLATFORM: "info", ContentItem.Scope.MOSQUE: "success"},
    )
    def scope_badge(self, obj):
        return obj.scope, obj.get_scope_display()

    @display(
        description="Модерация",
        ordering="moderation_status",
        label={
            ContentItem.ModerationStatus.PENDING: "warning",
            ContentItem.ModerationStatus.APPROVED: "success",
            ContentItem.ModerationStatus.REJECTED: "danger",
        },
    )
    def moderation_badge(self, obj):
        return obj.moderation_status, obj.get_moderation_status_display()

    @display(description="Публикация", label={"Опубликован": "success", "Черновик": "info"})
    def published_badge(self, obj):
        return "Опубликован" if obj.is_published else "Черновик"

    @display(description="Блокировка", label={"Заблокирован": "danger", "Активен": "success"})
    def blocked_badge(self, obj):
        return "Заблокирован" if obj.is_blocked else "Активен"

    @action(description="Одобрить", permissions=["approve_detail"], icon="publish", variant=ActionVariant.SUCCESS)
    def approve_detail(self, request, object_id):
        item = self.get_action_object(request, object_id)
        ContentService.approve(item=item, actor=request.user)
        self.notify_action(request, f"Материал «{item.title}» одобрен.")
        return self.redirect_to_change(item)

    def has_approve_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)

    @action(description="Отклонить", permissions=["reject_detail"], icon="block", variant=ActionVariant.DANGER)
    def reject_detail(self, request, object_id):
        item = self.get_action_object(request, object_id)
        ContentService.reject(item=item, actor=request.user)
        self.notify_action(request, f"Материал «{item.title}» отклонен.", level=messages.WARNING)
        return self.redirect_to_change(item)

    def has_reject_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)
