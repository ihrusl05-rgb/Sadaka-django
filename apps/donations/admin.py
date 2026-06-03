from django.contrib import admin
from django.contrib import messages

from unfold.contrib.filters.admin import ChoicesDropdownFilter, RangeDateTimeFilter, RelatedDropdownFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from apps.donations.models import Donation
from apps.donations.services import DonationService
from common.admin import ModelAdmin, MosqueScopedReadOnlyAdminMixin, admin_link_for


@admin.action(description="Подтвердить платежи")
def confirm_donations(modeladmin, request, queryset):
    updated = 0
    for donation in queryset.filter(status__in=[Donation.Status.PENDING, Donation.Status.PROCESSING]):
        DonationService.confirm_payment(donation=donation, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Подтверждено платежей: {updated}")


@admin.action(description="Отменить платежи")
def cancel_donations(modeladmin, request, queryset):
    updated = 0
    for donation in queryset.filter(status__in=[Donation.Status.PENDING, Donation.Status.PROCESSING]):
        DonationService.cancel_payment(donation=donation, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Отменено платежей: {updated}", level=messages.WARNING)


@admin.action(description="Оформить возврат")
def refund_donations(modeladmin, request, queryset):
    updated = 0
    for donation in queryset.filter(status=Donation.Status.SUCCEEDED):
        DonationService.refund_payment(donation=donation, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Возвращено платежей: {updated}", level=messages.WARNING)


@admin.register(Donation)
class DonationAdmin(MosqueScopedReadOnlyAdminMixin, ModelAdmin):
    actions = [confirm_donations, cancel_donations, refund_donations]
    actions_detail = ["confirm_detail", "cancel_detail", "refund_detail"]
    autocomplete_fields = ("user", "mosque", "project", "subscription")
    date_hierarchy = "paid_at"
    list_display = (
        "overview",
        "mosque_link",
        "project_link",
        "amount",
        "net_amount",
        "status_badge",
        "payment_method",
        "paid_badge",
    )
    list_filter = (
        ("status", ChoicesDropdownFilter),
        ("payment_method", ChoicesDropdownFilter),
        ("mosque", RelatedDropdownFilter),
        ("paid_at", RangeDateTimeFilter),
    )
    list_select_related = ("user", "mosque", "project", "subscription")
    readonly_fields = (
        "platform_fee_amount",
        "net_amount",
        "provider_payment_id",
        "receipt_number",
        "external_reference",
        "paid_at",
        "created_at",
        "updated_at",
        "deleted_at",
    )
    search_fields = ("user__email", "guest_email", "provider_payment_id", "receipt_number")
    fieldsets = (
        (
            "Основные сведения",
            {"fields": ("user", "guest_full_name", "guest_email", "is_public_anonymous", "mosque", "project", "subscription")},
        ),
        (
            "Суммы и оплата",
            {"fields": ("amount", "currency", "net_amount", "status", "payment_method")},
        ),
        (
            "Интеграция с провайдером",
            {"fields": ("provider", "provider_payment_id", "receipt_number", "external_reference", "paid_at")},
        ),
        ("Служебные данные", {"fields": ("metadata", "is_deleted", "deleted_at", "created_at", "updated_at")}),
    )

    def _belongs_to_managed_mosque(self, request, obj):
        return obj.mosque.memberships.filter(user=request.user).exists()

    @display(header=True, description="Пожертвование")
    def overview(self, obj):
        return [obj.donor_email, obj.receipt_number or f"ID {obj.id}", "DN"]

    @display(description="Мечеть")
    def mosque_link(self, obj):
        return admin_link_for(obj.mosque, label=obj.mosque.name)

    @display(description="Проект")
    def project_link(self, obj):
        return admin_link_for(obj.project, label=obj.project.title) if obj.project_id else "-"

    @display(
        description="Статус",
        ordering="status",
        label={
            Donation.Status.PENDING: "warning",
            Donation.Status.PROCESSING: "info",
            Donation.Status.SUCCEEDED: "success",
            Donation.Status.FAILED: "danger",
            Donation.Status.REFUNDED: "danger",
            Donation.Status.CANCELLED: "warning",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description="Оплата", label={"Оплачен": "success", "Не оплачен": "warning"})
    def paid_badge(self, obj):
        return "Оплачен" if obj.paid_at else "Не оплачен"

    @action(description="Подтвердить", permissions=["confirm_detail"], icon="check_circle", variant=ActionVariant.SUCCESS)
    def confirm_detail(self, request, object_id):
        donation = self.get_action_object(request, object_id, permission_check=self.has_view_permission)
        if donation.status not in {Donation.Status.PENDING, Donation.Status.PROCESSING}:
            self.notify_action(request, "Платеж уже обработан.", level=messages.WARNING)
            return self.redirect_to_change(donation)
        DonationService.confirm_payment(donation=donation, actor=request.user)
        self.notify_action(request, f"Платеж #{donation.id} подтвержден.")
        return self.redirect_to_change(donation)

    def has_confirm_detail_permission(self, request, object_id):
        return self.has_platform_action_permission(request, object_id, permission_check=self.has_view_permission)

    @action(description="Отменить", permissions=["cancel_detail"], icon="cancel", variant=ActionVariant.WARNING)
    def cancel_detail(self, request, object_id):
        donation = self.get_action_object(request, object_id, permission_check=self.has_view_permission)
        if donation.status not in {Donation.Status.PENDING, Donation.Status.PROCESSING}:
            self.notify_action(request, "Нельзя отменить платеж в текущем статусе.", level=messages.WARNING)
            return self.redirect_to_change(donation)
        DonationService.cancel_payment(donation=donation, actor=request.user)
        self.notify_action(request, f"Платеж #{donation.id} отменен.", level=messages.WARNING)
        return self.redirect_to_change(donation)

    def has_cancel_detail_permission(self, request, object_id):
        return self.has_platform_action_permission(request, object_id, permission_check=self.has_view_permission)

    @action(description="Возврат", permissions=["refund_detail"], icon="undo", variant=ActionVariant.DANGER)
    def refund_detail(self, request, object_id):
        donation = self.get_action_object(request, object_id, permission_check=self.has_view_permission)
        if donation.status != Donation.Status.SUCCEEDED:
            self.notify_action(request, "Возврат возможен только для оплаченного платежа.", level=messages.WARNING)
            return self.redirect_to_change(donation)
        DonationService.refund_payment(donation=donation, actor=request.user)
        self.notify_action(request, f"Платеж #{donation.id} возвращен.", level=messages.WARNING)
        return self.redirect_to_change(donation)

    def has_refund_detail_permission(self, request, object_id):
        return self.has_platform_action_permission(request, object_id, permission_check=self.has_view_permission)
