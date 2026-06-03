from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.models import Group
from django.db.models import Exists, OuterRef

from unfold.contrib.filters.admin import BooleanRadioFilter, ChoicesDropdownFilter, RangeDateTimeFilter
from unfold.forms import AdminPasswordChangeForm as UnfoldAdminPasswordChangeForm
from unfold.forms import UnfoldReadOnlyPasswordHashWidget
from unfold.widgets import UnfoldAdminPasswordWidget

from apps.users.models import MaxAccount, MaxAuthCode, MaxLoginToken, TelegramAccount, TelegramAuthCode, TelegramLoginToken, User
from common.admin import ModelAdmin, PlatformOnlyAdminMixin


class TelegramLinkedFilter(admin.SimpleListFilter):
    title = "Telegram"
    parameter_name = "telegram_linked"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Привязан"),
            ("no", "Не привязан"),
        )

    def queryset(self, request, queryset):
        telegram_accounts = TelegramAccount.objects.filter(user_id=OuterRef("pk"))
        annotated = queryset.annotate(has_telegram_account=Exists(telegram_accounts))
        if self.value() == "yes":
            return annotated.filter(has_telegram_account=True)
        if self.value() == "no":
            return annotated.filter(has_telegram_account=False)
        return annotated


class UserAdminCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Пароль",
        widget=UnfoldAdminPasswordWidget(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=UnfoldAdminPasswordWidget(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("email", "full_name", "last_name", "first_name", "middle_name", "phone", "photo", "role")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Пароли не совпадают.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserAdminChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label="Пароль",
        help_text="Сырые пароли не хранятся, поэтому посмотреть текущий пароль нельзя.",
        widget=UnfoldReadOnlyPasswordHashWidget(),
    )

    class Meta:
        model = User
        fields = "__all__"

    def clean_password(self):
        return self.initial["password"]


@admin.register(User)
class UserAdmin(PlatformOnlyAdminMixin, BaseUserAdmin, ModelAdmin):
    add_form = UserAdminCreationForm
    change_password_form = UnfoldAdminPasswordChangeForm
    form = UserAdminChangeForm
    date_hierarchy = "date_joined"
    list_display = ("email", "full_name", "phone", "role", "telegram_username", "is_blocked", "is_staff", "date_joined")
    list_filter = (
        ("role", ChoicesDropdownFilter),
        TelegramLinkedFilter,
        ("is_blocked", BooleanRadioFilter),
        ("is_staff", BooleanRadioFilter),
        ("is_email_verified", BooleanRadioFilter),
        ("date_joined", RangeDateTimeFilter),
    )
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_activity_at", "blocked_at", "created_at", "updated_at", "telegram_summary")
    search_fields = ("email", "full_name", "last_name", "first_name", "middle_name", "phone", "telegram_account__username", "telegram_account__telegram_id")
    fieldsets = (
        ("Основная информация", {"fields": ("email", "password", "full_name", "last_name", "first_name", "middle_name", "phone", "photo", "role")}),
        (
            "Статус доступа",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_blocked",
                    "blocked_at",
                    "is_email_verified",
                )
            },
        ),
        ("Telegram", {"fields": ("telegram_summary",)}),
        ("Права доступа", {"fields": ("groups", "user_permissions")}),
        ("Служебные поля", {"fields": ("last_activity_at", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            "Основная информация",
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "last_name", "first_name", "middle_name", "phone", "photo", "role", "password1", "password2"),
            },
        ),
        (
            "Статус доступа",
            {
                "classes": ("wide",),
                "fields": ("is_active", "is_staff", "is_superuser", "is_blocked", "is_email_verified", "is_phone_verified"),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")

    @admin.display(description="Telegram")
    def telegram_username(self, obj):
        if hasattr(obj, "telegram_account"):
            account = obj.telegram_account
            if account.username:
                return f"@{account.username}"
            return account.telegram_id
        return "—"

    @admin.display(description="Telegram")
    def telegram_summary(self, obj):
        if not hasattr(obj, "telegram_account"):
            return "Не привязан"
        account = obj.telegram_account
        parts = [f"ID: {account.telegram_id}"]
        if account.username:
            parts.append(f"@{account.username}")
        if account.chat_id:
            parts.append(f"chat: {account.chat_id}")
        return " · ".join(str(part) for part in parts)


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(PlatformOnlyAdminMixin, BaseGroupAdmin, ModelAdmin):
    search_fields = ("name",)


@admin.register(TelegramAccount)
class TelegramAccountAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    list_display = ("telegram_id", "username", "user", "chat_id", "linked_at")
    readonly_fields = ("linked_at", "created_at", "updated_at")
    search_fields = ("telegram_id", "username", "first_name", "last_name", "user__email", "user__full_name")
    list_filter = (("linked_at", RangeDateTimeFilter), ("created_at", RangeDateTimeFilter))


@admin.register(TelegramLoginToken)
class TelegramLoginTokenAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    list_display = ("token", "telegram_account", "user", "confirmed_at", "completed_at", "expires_at", "created_at")
    readonly_fields = (
        "token",
        "user",
        "telegram_account",
        "confirmed_at",
        "completed_at",
        "code_sent_at",
        "expires_at",
        "requested_by_ip",
        "user_agent",
        "created_at",
        "updated_at",
    )
    search_fields = ("token", "telegram_account__username", "telegram_account__telegram_id", "user__email")
    list_filter = (
        ("confirmed_at", RangeDateTimeFilter),
        ("completed_at", RangeDateTimeFilter),
        ("expires_at", RangeDateTimeFilter),
        ("created_at", RangeDateTimeFilter),
    )


@admin.register(TelegramAuthCode)
class TelegramAuthCodeAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    list_display = ("telegram_id", "user", "attempts", "used_at", "expires_at", "created_at")
    readonly_fields = (
        "user",
        "telegram_account",
        "login_token",
        "telegram_id",
        "code_hash",
        "attempts",
        "max_attempts",
        "used_at",
        "expires_at",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    )
    search_fields = ("telegram_id", "telegram_account__username", "user__email")
    list_filter = (("used_at", RangeDateTimeFilter), ("expires_at", RangeDateTimeFilter), ("created_at", RangeDateTimeFilter))


@admin.register(MaxAccount)
class MaxAccountAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    list_display = ("max_user_id", "username", "user", "chat_id", "linked_at")
    readonly_fields = ("linked_at", "created_at", "updated_at")
    search_fields = ("max_user_id", "username", "first_name", "last_name", "user__email", "user__full_name")
    list_filter = (("linked_at", RangeDateTimeFilter), ("created_at", RangeDateTimeFilter))


@admin.register(MaxLoginToken)
class MaxLoginTokenAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    list_display = ("token", "max_account", "user", "confirmed_at", "completed_at", "expires_at", "created_at")
    readonly_fields = (
        "token",
        "user",
        "max_account",
        "confirmed_at",
        "completed_at",
        "code_sent_at",
        "expires_at",
        "requested_by_ip",
        "user_agent",
        "created_at",
        "updated_at",
    )
    search_fields = ("token", "max_account__username", "max_account__max_user_id", "user__email")
    list_filter = (
        ("confirmed_at", RangeDateTimeFilter),
        ("completed_at", RangeDateTimeFilter),
        ("expires_at", RangeDateTimeFilter),
        ("created_at", RangeDateTimeFilter),
    )


@admin.register(MaxAuthCode)
class MaxAuthCodeAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    list_display = ("max_user_id", "user", "attempts", "used_at", "expires_at", "created_at")
    readonly_fields = (
        "user",
        "max_account",
        "login_token",
        "max_user_id",
        "code_hash",
        "attempts",
        "max_attempts",
        "used_at",
        "expires_at",
        "ip_address",
        "user_agent",
        "created_at",
        "updated_at",
    )
    search_fields = ("max_user_id", "max_account__username", "user__email")
    list_filter = (("used_at", RangeDateTimeFilter), ("expires_at", RangeDateTimeFilter), ("created_at", RangeDateTimeFilter))
