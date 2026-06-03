from django.contrib import admin

from unfold.contrib.filters.admin import RangeDateTimeFilter
from unfold.decorators import display

from apps.platform.models import AuditLog, MosqueSiteRequest, PlatformSettings
from common.admin import ModelAdmin, PlatformOnlyAdminMixin


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    list_display = ("site_name", "support_email", "donations_enabled")
    readonly_fields = ("default_commission_percent", "created_at", "updated_at")
    fieldsets = (
        ("Основные настройки", {"fields": ("site_name", "support_email")}),
        ("Финансы и доступность", {"fields": ("donations_enabled",)}),
        ("Служебные поля", {"fields": ("default_commission_percent", "created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not PlatformSettings.objects.exists()


@admin.register(AuditLog)
class AuditLogAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    ACTION_LABELS = {
        "user.registered": "Пользователь зарегистрирован",
        "user.logged_in": "Пользователь вошел в систему",
        "user.logged_out": "Пользователь вышел из системы",
        "user.profile_updated": "Профиль пользователя обновлен",
        "user.password_changed": "Пароль пользователя изменен",
        "user.password_reset_requested": "Запрошен сброс пароля",
        "user.password_reset_confirmed": "Сброс пароля подтвержден",
        "user.blocked": "Пользователь заблокирован",
        "mosque.created": "Мечеть создана",
        "mosque.updated": "Мечеть обновлена",
        "mosque.approved": "Мечеть одобрена",
        "mosque.rejected": "Мечеть отклонена",
        "mosque.verified": "Мечеть подтверждена",
        "mosque.blocked": "Мечеть заблокирована",
        "mosque.unblocked": "Мечеть разблокирована",
        "project.created": "Проект создан",
        "project.updated": "Проект обновлен",
        "project.approved": "Проект одобрен",
        "project.rejected": "Проект отклонен",
        "project.blocked": "Проект заблокирован",
        "content.created": "Контент создан",
        "content.updated": "Контент обновлен",
        "content.approved": "Контент одобрен",
        "content.rejected": "Контент отклонен",
        "donation.created": "Пожертвование создано",
        "donation.confirmed": "Пожертвование подтверждено",
        "donation.cancelled": "Пожертвование отменено",
        "donation.refunded": "Пожертвование возвращено",
        "subscription.created": "Подписка создана",
        "subscription.updated": "Подписка обновлена",
        "subscription.cancelled": "Подписка отменена",
        "subscription.charged": "Подписка списана",
        "complaint.created": "Жалоба создана",
        "complaint.handled": "Жалоба обработана",
        "notification.created": "Уведомление создано",
        "notification.read": "Уведомление прочитано",
        "report.requested": "Отчет запрошен",
        "report.generated": "Отчет сформирован",
    }

    date_hierarchy = "created_at"
    list_display = ("action_display", "actor", "object_model", "object_id", "created_at")
    list_filter = ("action", ("created_at", RangeDateTimeFilter))
    list_select_related = ("actor", "content_type")
    readonly_fields = (
        "actor",
        "action",
        "content_type",
        "object_id",
        "model_label",
        "metadata",
        "ip_address",
        "created_at",
        "updated_at",
    )
    search_fields = ("action", "actor__email", "model_label", "object_id")

    @display(description="Действие")
    def action_display(self, obj):
        return self.ACTION_LABELS.get(obj.action, obj.action)

    @display(description="Модель")
    def object_model(self, obj):
        if obj.content_type_id and obj.content_type.model_class():
            return obj.content_type.model_class()._meta.verbose_name
        return obj.model_label


@admin.register(MosqueSiteRequest)
class MosqueSiteRequestAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    date_hierarchy = "created_at"
    list_display = ("id", "mosque_name", "request_type", "status", "phone", "created_at", "reviewed_at")
    list_filter = ("request_type", "status", ("created_at", RangeDateTimeFilter))
    search_fields = ("mosque_name", "full_name", "phone", "city", "region", "comment")
    readonly_fields = ("created_at", "updated_at", "reviewed_at", "reviewed_by_telegram_id", "reviewed_by_username")
