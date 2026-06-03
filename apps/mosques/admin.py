from django.contrib import admin
from django.contrib import messages
from django.db.models import Q

from unfold.contrib.filters.admin import BooleanRadioFilter, ChoicesDropdownFilter
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from apps.mosques.models import Mosque, MosqueDocument, MosqueExpenseItem, MosqueGalleryImage, MosqueMembership, MosquePartner
from apps.mosques.services import MosqueService
from common.admin import ModelAdmin, MosqueScopedAdminMixin, TabularInline, admin_link_for


class MosqueMembershipInline(TabularInline):
    model = MosqueMembership
    extra = 0
    show_change_link = True
    fields = ("user", "is_primary", "created_at")
    readonly_fields = ("created_at",)
    verbose_name = "Администратор мечети"
    verbose_name_plural = "Администраторы мечети"


class MosqueGalleryImageInline(TabularInline):
    model = MosqueGalleryImage
    extra = 0
    fields = ("image", "caption", "sort_order", "created_at")
    readonly_fields = ("created_at",)
    verbose_name = "Фотография"
    verbose_name_plural = "Фотографии"


class MosqueExpenseItemInline(TabularInline):
    model = MosqueExpenseItem
    extra = 0
    fields = ("title", "amount", "sort_order", "created_at")
    readonly_fields = ("created_at",)
    verbose_name = "Статья расходов"
    verbose_name_plural = "Статьи расходов"


class MosqueDocumentInline(TabularInline):
    model = MosqueDocument
    extra = 0
    fields = ("title", "file", "sort_order", "created_at")
    readonly_fields = ("created_at",)
    verbose_name = "Документ"
    verbose_name_plural = "Документы"


class MosquePartnerInline(TabularInline):
    model = MosquePartner
    extra = 0
    fields = ("name", "website_url", "logo", "sort_order", "created_at")
    readonly_fields = ("created_at",)
    verbose_name = "Партнер"
    verbose_name_plural = "Партнеры"


@admin.action(description="Одобрить выбранные мечети")
def approve_mosques(modeladmin, request, queryset):
    updated = 0
    for mosque in queryset:
        MosqueService.approve(mosque=mosque, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Одобрено мечетей: {updated}")


@admin.action(description="Отклонить выбранные мечети")
def reject_mosques(modeladmin, request, queryset):
    updated = 0
    for mosque in queryset:
        MosqueService.reject(mosque=mosque, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Отклонено мечетей: {updated}")


@admin.action(description="Подтвердить выбранные мечети")
def verify_mosques(modeladmin, request, queryset):
    updated = 0
    for mosque in queryset:
        MosqueService.verify(mosque=mosque, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Подтверждено мечетей: {updated}")


@admin.action(description="Заблокировать выбранные мечети")
def block_mosques(modeladmin, request, queryset):
    updated = 0
    for mosque in queryset:
        MosqueService.block(mosque=mosque, actor=request.user, reason="Admin bulk action")
        updated += 1
    modeladmin.notify_action(request, f"Заблокировано мечетей: {updated}", level=messages.WARNING)


@admin.action(description="Разблокировать выбранные мечети")
def unblock_mosques(modeladmin, request, queryset):
    updated = 0
    for mosque in queryset:
        MosqueService.unblock(mosque=mosque, actor=request.user)
        updated += 1
    modeladmin.notify_action(request, f"Разблокировано мечетей: {updated}")


@admin.register(Mosque)
class MosqueAdmin(MosqueScopedAdminMixin, ModelAdmin):
    actions = [approve_mosques, reject_mosques, verify_mosques, block_mosques, unblock_mosques]
    actions_detail = [
        "approve_detail",
        "reject_detail",
        "verify_detail",
        "block_detail",
        "unblock_detail",
    ]
    autocomplete_fields = ("featured_project",)
    prepopulated_fields = {"slug": ("name",)}
    date_hierarchy = "created_at"
    inlines = [
        MosqueMembershipInline,
        MosqueGalleryImageInline,
        MosqueExpenseItemInline,
        MosqueDocumentInline,
        MosquePartnerInline,
    ]
    list_display = (
        "overview",
        "moderation_badge",
        "verification_badge",
        "primary_admin",
        "published_at",
        "blocked_badge",
    )
    list_filter = (
        ("moderation_status", ChoicesDropdownFilter),
        ("verification_status", ChoicesDropdownFilter),
        ("is_blocked", BooleanRadioFilter),
    )
    readonly_fields = ("created_by", "published_at", "blocked_at", "created_at", "updated_at", "deleted_at")
    search_fields = ("name", "city", "contact_email", "contact_phone")
    fieldsets = (
        (
            "Основные сведения",
            {"fields": ("name", "slug", "description", "public_story", "city", "address", "created_by")},
        ),
        ("Контакты", {"fields": ("contact_email", "contact_phone")}),
        (
            "Публичное оформление",
            {"fields": ("cover_image", "featured_project")},
        ),
        (
            "Юридическая информация",
            {
                "fields": (
                    "legal_name",
                    "inn",
                    "kpp",
                    "ogrn",
                    "bank_account",
                    "bank_name",
                    "bik",
                    "corr_account",
                    "legal_address",
                    "actual_address",
                    "okpo",
                    "oktmo",
                    "okato",
                )
            },
        ),
        (
            "Статусы и модерация",
            {"fields": ("verification_status", "moderation_status", "is_blocked", "blocked_at", "blocked_reason")},
        ),
        ("Публикация", {"fields": ("published_at",)}),
        ("Служебные поля", {"fields": ("is_deleted", "deleted_at", "created_at", "updated_at")}),
    )

    def get_mosque_scope_q(self, request):
        return Q(memberships__user=request.user)

    def _belongs_to_managed_mosque(self, request, obj):
        return obj.memberships.filter(user=request.user).exists()

    @display(header=True, description="Мечеть")
    def overview(self, obj):
        return [obj.name, obj.city, "MS"]

    @display(
        description="Модерация",
        ordering="moderation_status",
        label={
            Mosque.ModerationStatus.PENDING: "warning",
            Mosque.ModerationStatus.APPROVED: "success",
            Mosque.ModerationStatus.REJECTED: "danger",
        },
    )
    def moderation_badge(self, obj):
        return obj.moderation_status, obj.get_moderation_status_display()

    @display(
        description="Верификация",
        ordering="verification_status",
        label={
            Mosque.VerificationStatus.PENDING: "warning",
            Mosque.VerificationStatus.VERIFIED: "success",
            Mosque.VerificationStatus.REJECTED: "danger",
        },
    )
    def verification_badge(self, obj):
        return obj.verification_status, obj.get_verification_status_display()

    @display(description="Главный админ")
    def primary_admin(self, obj):
        membership = obj.memberships.select_related("user").filter(is_primary=True).first() or obj.memberships.select_related("user").first()
        if not membership:
            return "-"
        if getattr(self, "request", None) and self.request.user.is_platform_admin:
            return admin_link_for(membership.user, label=membership.user.email)
        return membership.user.email

    @display(description="Блокировка", label={"Заблокирована": "danger", "Активна": "success"})
    def blocked_badge(self, obj):
        return "Заблокирована" if obj.is_blocked else "Активна"

    @action(description="Одобрить", permissions=["approve_detail"], icon="check_circle", variant=ActionVariant.SUCCESS)
    def approve_detail(self, request, object_id):
        mosque = self.get_action_object(request, object_id)
        MosqueService.approve(mosque=mosque, actor=request.user)
        self.notify_action(request, f"Мечеть «{mosque.name}» одобрена.")
        return self.redirect_to_change(mosque)

    def has_approve_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)

    @action(description="Отклонить", permissions=["reject_detail"], icon="cancel", variant=ActionVariant.DANGER)
    def reject_detail(self, request, object_id):
        mosque = self.get_action_object(request, object_id)
        MosqueService.reject(mosque=mosque, actor=request.user)
        self.notify_action(request, f"Мечеть «{mosque.name}» отклонена.", level=messages.WARNING)
        return self.redirect_to_change(mosque)

    def has_reject_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)

    @action(description="Подтвердить", permissions=["verify_detail"], icon="verified", variant=ActionVariant.INFO)
    def verify_detail(self, request, object_id):
        mosque = self.get_action_object(request, object_id)
        MosqueService.verify(mosque=mosque, actor=request.user)
        self.notify_action(request, f"Мечеть «{mosque.name}» подтверждена.")
        return self.redirect_to_change(mosque)

    def has_verify_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)

    @action(description="Заблокировать", permissions=["block_detail"], icon="block", variant=ActionVariant.WARNING)
    def block_detail(self, request, object_id):
        mosque = self.get_action_object(request, object_id)
        MosqueService.block(mosque=mosque, actor=request.user, reason="Admin detail action")
        self.notify_action(request, f"Мечеть «{mosque.name}» заблокирована.", level=messages.WARNING)
        return self.redirect_to_change(mosque)

    def has_block_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)

    @action(description="Разблокировать", permissions=["unblock_detail"], icon="lock_open", variant=ActionVariant.SUCCESS)
    def unblock_detail(self, request, object_id):
        mosque = self.get_action_object(request, object_id)
        MosqueService.unblock(mosque=mosque, actor=request.user)
        self.notify_action(request, f"Мечеть «{mosque.name}» разблокирована.")
        return self.redirect_to_change(mosque)

    def has_unblock_detail_permission(self, request, object_id):
        return self.has_action_permission(request, object_id)
