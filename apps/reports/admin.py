from django.contrib import admin
from django.db.models import Q

from unfold.contrib.filters.admin import ChoicesDropdownFilter, RangeDateFilter, RelatedDropdownFilter
from unfold.decorators import display

from apps.reports.models import Report
from common.admin import ModelAdmin, MosqueScopedAdminMixin


@admin.register(Report)
class ReportAdmin(MosqueScopedAdminMixin, ModelAdmin):
    autocomplete_fields = ("mosque", "project")
    date_hierarchy = "period_start"
    list_display = ("overview", "scope_badge", "format", "status_badge", "period_start", "period_end")
    list_filter = (
        ("scope_type", ChoicesDropdownFilter),
        ("format", ChoicesDropdownFilter),
        ("status", ChoicesDropdownFilter),
        ("period_start", RangeDateFilter),
        ("mosque", RelatedDropdownFilter),
    )
    list_select_related = ("requested_by", "mosque", "project")
    readonly_fields = ("requested_by", "file", "error_message", "created_at", "updated_at", "deleted_at")
    search_fields = ("requested_by__email",)
    fieldsets = (
        ("Основные сведения", {"fields": ("requested_by", "scope_type", "mosque", "project", "format")}),
        ("Период и статус", {"fields": ("period_start", "period_end", "status")}),
        ("Результат генерации", {"fields": ("file", "error_message")}),
        ("Служебные поля", {"fields": ("is_deleted", "deleted_at", "created_at", "updated_at")}),
    )

    restrict_user_fields = ("requested_by",)

    def get_mosque_scope_q(self, request):
        return Q(mosque__memberships__user=request.user) | Q(project__mosque__memberships__user=request.user)

    def _belongs_to_managed_mosque(self, request, obj):
        if obj.mosque_id:
            return obj.mosque.memberships.filter(user=request.user).exists()
        if obj.project_id:
            return obj.project.mosque.memberships.filter(user=request.user).exists()
        return False

    @display(header=True, description="Отчет")
    def overview(self, obj):
        target = obj.project.title if obj.project_id else obj.mosque.name if obj.mosque_id else "Платформа"
        return [f"Отчет #{obj.id}", target, "RP"]

    @display(
        description="Область",
        ordering="scope_type",
        label={
            Report.ScopeType.PLATFORM: "info",
            Report.ScopeType.MOSQUE: "success",
            Report.ScopeType.PROJECT: "warning",
        },
    )
    def scope_badge(self, obj):
        return obj.scope_type, obj.get_scope_type_display()

    @display(
        description="Статус",
        ordering="status",
        label={
            Report.Status.QUEUED: "warning",
            Report.Status.GENERATING: "info",
            Report.Status.READY: "success",
            Report.Status.FAILED: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()
