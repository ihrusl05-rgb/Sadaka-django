from django.contrib import admin
from django.contrib import messages

from unfold.contrib.filters.admin import ChoicesDropdownFilter, RangeDateFilter, RelatedDropdownFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from apps.subscriptions.models import Subscription
from apps.subscriptions.services import SubscriptionService
from common.admin import ModelAdmin, MosqueScopedReadOnlyAdminMixin, admin_link_for


@admin.action(description="Отменить выбранные подписки")
def cancel_subscriptions(modeladmin, request, queryset):
    updated = 0
    for subscription in queryset.exclude(status=Subscription.Status.CANCELLED):
        SubscriptionService.cancel_subscription(subscription=subscription, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Отменено подписок: {updated}", level=messages.WARNING)


@admin.register(Subscription)
class SubscriptionAdmin(MosqueScopedReadOnlyAdminMixin, ModelAdmin):
    actions = [cancel_subscriptions]
    actions_detail = ["cancel_detail"]
    autocomplete_fields = ("user", "mosque", "project")
    date_hierarchy = "next_charge_date"
    list_display = (
        "overview",
        "mosque_link",
        "project_link",
        "amount",
        "interval",
        "status_badge",
        "next_charge_date",
        "last_charged_at",
    )
    list_filter = (
        ("status", ChoicesDropdownFilter),
        ("interval", ChoicesDropdownFilter),
        ("mosque", RelatedDropdownFilter),
        ("next_charge_date", RangeDateFilter),
    )
    list_select_related = ("user", "mosque", "project")
    readonly_fields = ("provider_subscription_id", "last_charged_at", "cancelled_at", "created_at", "updated_at", "deleted_at")
    search_fields = ("user__email", "guest_email", "provider_subscription_id")
    fieldsets = (
        (
            "Основные сведения",
            {"fields": ("user", "guest_full_name", "guest_email", "is_public_anonymous", "mosque", "project", "amount", "currency")},
        ),
        ("Параметры списания", {"fields": ("interval", "status", "next_charge_date", "last_charged_at", "cancelled_at")}),
        ("Интеграция с провайдером", {"fields": ("payment_method", "provider", "provider_subscription_id")}),
        ("Служебные данные", {"fields": ("metadata", "is_deleted", "deleted_at", "created_at", "updated_at")}),
    )

    def _belongs_to_managed_mosque(self, request, obj):
        return obj.mosque.memberships.filter(user=request.user).exists()

    @display(header=True, description="Подписка")
    def overview(self, obj):
        return [obj.donor_email, obj.provider_subscription_id or f"sub_{obj.id}", "SB"]

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
            Subscription.Status.ACTIVE: "success",
            Subscription.Status.PAUSED: "warning",
            Subscription.Status.CANCELLED: "danger",
            Subscription.Status.PAST_DUE: "danger",
        },
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @action(description="Отменить", permissions=["cancel_detail"], icon="event_busy", variant=ActionVariant.DANGER)
    def cancel_detail(self, request, object_id):
        subscription = self.get_action_object(request, object_id, permission_check=self.has_view_permission)
        if subscription.status == Subscription.Status.CANCELLED:
            self.notify_action(request, "Подписка уже отменена.", level=messages.WARNING)
            return self.redirect_to_change(subscription)
        SubscriptionService.cancel_subscription(subscription=subscription, actor=request.user)
        self.notify_action(request, f"Подписка #{subscription.id} отменена.", level=messages.WARNING)
        return self.redirect_to_change(subscription)

    def has_cancel_detail_permission(self, request, object_id):
        return self.has_platform_action_permission(request, object_id, permission_check=self.has_view_permission)
