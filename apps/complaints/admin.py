from django.contrib import admin
from django.contrib import messages

from unfold.contrib.filters.admin import ChoicesDropdownFilter, RelatedDropdownFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from apps.complaints.models import Complaint
from apps.complaints.services import ComplaintService
from common.admin import ModelAdmin, PlatformOnlyAdminMixin


class ComplaintStatusFilter(admin.SimpleListFilter):
    title = "Состояние обработки"
    parameter_name = "processing"

    def lookups(self, request, model_admin):
        return (
            ("open", "Требуют внимания"),
            ("done", "Обработанные"),
        )

    def queryset(self, request, queryset):
        if self.value() == "open":
            return queryset.filter(status__in=[Complaint.Status.NEW, Complaint.Status.IN_REVIEW])
        if self.value() == "done":
            return queryset.filter(status__in=[Complaint.Status.RESOLVED, Complaint.Status.REJECTED])
        return queryset


@admin.action(description="Взять в работу")
def mark_in_review(modeladmin, request, queryset):
    updated = 0
    for complaint in queryset.exclude(status=Complaint.Status.IN_REVIEW):
        ComplaintService.handle_complaint(
            complaint=complaint,
            actor=request.user,
            status=Complaint.Status.IN_REVIEW,
            resolution_note=complaint.resolution_note or "Взято в работу из админки.",
        )
        updated += 1
    modeladmin.notify_action(request, f"Жалоб взято в работу: {updated}")


@admin.action(description="Решить жалобы")
def resolve_complaints(modeladmin, request, queryset):
    updated = 0
    for complaint in queryset.exclude(status=Complaint.Status.RESOLVED):
        ComplaintService.handle_complaint(
            complaint=complaint,
            actor=request.user,
            status=Complaint.Status.RESOLVED,
            resolution_note=complaint.resolution_note or "Решено из админки.",
        )
        updated += 1
    modeladmin.notify_action(request, f"Жалоб решено: {updated}")


@admin.action(description="Отклонить жалобы")
def reject_complaints(modeladmin, request, queryset):
    updated = 0
    for complaint in queryset.exclude(status=Complaint.Status.REJECTED):
        ComplaintService.handle_complaint(
            complaint=complaint,
            actor=request.user,
            status=Complaint.Status.REJECTED,
            resolution_note=complaint.resolution_note or "Отклонено из админки.",
        )
        updated += 1
    modeladmin.notify_action(request, f"Жалоб отклонено: {updated}", level=messages.WARNING)


@admin.register(Complaint)
class ComplaintAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    actions = [mark_in_review, resolve_complaints, reject_complaints]
    actions_detail = ["mark_in_review_detail", "resolve_detail", "reject_detail"]
    autocomplete_fields = ("user", "handled_by")
    date_hierarchy = "created_at"
    list_display = ("overview", "target_model", "status_badge", "handled_by", "handled_at", "created_at")
    list_filter = (ComplaintStatusFilter, ("status", ChoicesDropdownFilter), ("content_type", RelatedDropdownFilter))
    list_select_related = ("user", "content_type", "handled_by")
    readonly_fields = ("created_at", "updated_at", "deleted_at", "handled_at", "handled_by")
    search_fields = ("user__email", "description")
    fieldsets = (
        ("Основные сведения", {"fields": ("user", "content_type", "object_id", "description")}),
        ("Рассмотрение", {"fields": ("status", "resolution_note", "handled_by", "handled_at")}),
        ("Служебные поля", {"fields": ("is_deleted", "deleted_at", "created_at", "updated_at")}),
    )

    @display(header=True, description="Жалоба")
    def overview(self, obj):
        return [obj.user.email, obj.created_at.strftime("%d.%m.%Y %H:%M"), "CP"]

    @display(description="Объект жалобы")
    def target_model(self, obj):
        if obj.target:
            return f"{obj.target._meta.verbose_name} #{obj.object_id}"
        return f"{obj.content_type} #{obj.object_id}"

    @display(
        description="Статус",
        ordering="status",
        label={
            Complaint.Status.NEW: "warning",
            Complaint.Status.IN_REVIEW: "info",
            Complaint.Status.RESOLVED: "success",
            Complaint.Status.REJECTED: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    def _change_status(self, request, object_id, *, status, note, message, level=messages.SUCCESS):
        complaint = self.get_object(request, object_id)
        ComplaintService.handle_complaint(
            complaint=complaint,
            actor=request.user,
            status=status,
            resolution_note=note,
        )
        self.notify_action(request, message, level=level)
        return self.redirect_to_change(complaint)

    @action(description="В работу", permissions=["change"], icon="assignment", variant=ActionVariant.INFO)
    def mark_in_review_detail(self, request, object_id):
        return self._change_status(
            request,
            object_id,
            status=Complaint.Status.IN_REVIEW,
            note="Взято в работу из карточки.",
            message="Жалоба взята в работу.",
        )

    @action(description="Решить", permissions=["change"], icon="task_alt", variant=ActionVariant.SUCCESS)
    def resolve_detail(self, request, object_id):
        return self._change_status(
            request,
            object_id,
            status=Complaint.Status.RESOLVED,
            note="Решено из карточки.",
            message="Жалоба решена.",
        )

    @action(description="Отклонить", permissions=["change"], icon="block", variant=ActionVariant.DANGER)
    def reject_detail(self, request, object_id):
        return self._change_status(
            request,
            object_id,
            status=Complaint.Status.REJECTED,
            note="Отклонено из карточки.",
            message="Жалоба отклонена.",
            level=messages.WARNING,
        )
