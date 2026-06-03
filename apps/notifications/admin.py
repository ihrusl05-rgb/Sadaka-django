from django import forms
from django.contrib import admin, messages
from django.db import models
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse

from unfold.contrib.filters.admin import BooleanRadioFilter, ChoicesDropdownFilter
from unfold.decorators import display

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.users.models import User
from common.admin import ModelAdmin, PlatformOnlyAdminMixin


class NotificationAdminForm(forms.ModelForm):
    class SendScope(models.TextChoices):
        SINGLE = "single", "Одному пользователю"
        SELECTED = "selected", "Выбранным пользователям"
        ALL_USERS = "all_users", "Всем пользователям"
        MOSQUE_ADMINS = "mosque_admins", "Всем администраторам мечетей"
        PLATFORM_ADMINS = "platform_admins", "Всем администраторам платформы"
        SYSTEM = "system", "Системное уведомление platform admin"

    send_scope = forms.ChoiceField(
        label="Кому отправить",
        choices=SendScope.choices,
        initial=SendScope.SINGLE,
        help_text="Массовая отправка создаёт отдельное уведомление для каждого получателя.",
    )
    recipients = forms.ModelMultipleChoiceField(
        label="Выбранные пользователи",
        queryset=User.objects.none(),
        required=False,
        help_text="Используется только для варианта «Выбранным пользователям».",
        widget=admin.widgets.FilteredSelectMultiple("Пользователи", is_stacked=False),
    )

    class Meta:
        model = Notification
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["recipients"].queryset = User.objects.filter(is_deleted=False, is_active=True).order_by("email")

        if self.instance.pk:
            initial_scope = self.SendScope.SYSTEM if self.instance.user_id is None else self.SendScope.SINGLE
            self.fields["send_scope"].initial = initial_scope
            self.fields["send_scope"].disabled = True
            self.fields["recipients"].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk:
            return cleaned_data

        send_scope = cleaned_data.get("send_scope")
        user = cleaned_data.get("user")
        recipients = cleaned_data.get("recipients")

        if send_scope == self.SendScope.SINGLE and not user:
            self.add_error("user", "Выберите пользователя для персонального уведомления.")

        if send_scope == self.SendScope.SELECTED and not recipients:
            self.add_error("recipients", "Выберите хотя бы одного пользователя.")

        if send_scope != self.SendScope.SINGLE:
            cleaned_data["user"] = None

        return cleaned_data


@admin.register(Notification)
class NotificationAdmin(PlatformOnlyAdminMixin, ModelAdmin):
    form = NotificationAdminForm
    autocomplete_fields = ("user",)
    date_hierarchy = "created_at"
    list_display = ("id", "user", "title", "notification_type", "event", "is_read_badge", "created_at")
    list_filter = (
        ("notification_type", ChoicesDropdownFilter),
        ("event", ChoicesDropdownFilter),
        ("is_read", BooleanRadioFilter),
    )
    list_select_related = ("user",)
    readonly_fields = ("read_at", "created_at", "updated_at", "deleted_at")
    search_fields = ("user__email", "title", "message")
    actions = ("mark_selected_read", "mark_selected_unread")
    fieldsets = (
        ("Кому доставить", {"fields": ("send_scope", "recipients", "user")}),
        ("Основные сведения", {"fields": ("title", "notification_type", "event", "link")}),
        ("Текст и данные", {"fields": ("message", "payload")}),
        ("Звук и статусы", {"fields": ("is_sound_enabled", "sound_key", "is_read", "read_at")}),
        ("Служебные поля", {"fields": ("is_deleted", "deleted_at", "created_at", "updated_at")}),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is not None:
            fieldsets[0] = ("Кому доставить", {"fields": ("send_scope", "user")})
        return fieldsets

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("send_scope", NotificationAdminForm.SendScope.SINGLE)
        return initial

    def save_model(self, request, obj, form, change):
        if change:
            return super().save_model(request, obj, form, change)

        send_scope = form.cleaned_data.get("send_scope")
        if send_scope in {NotificationAdminForm.SendScope.SINGLE, NotificationAdminForm.SendScope.SYSTEM}:
            return super().save_model(request, obj, form, change)

        recipients = self._resolve_recipients(send_scope=send_scope, form=form)
        created_count = 0
        for recipient in recipients:
            notification = NotificationService.create_notification(
                user=recipient,
                title=form.cleaned_data["title"],
                message=form.cleaned_data["message"],
                event=form.cleaned_data.get("event") or "",
                notification_type=form.cleaned_data["notification_type"],
                link=form.cleaned_data.get("link") or "",
                payload=form.cleaned_data.get("payload") or {},
                sound_key=form.cleaned_data.get("sound_key") or "default",
                is_sound_enabled=form.cleaned_data.get("is_sound_enabled", True),
            )
            if notification is not None:
                created_count += 1

        request._notification_bulk_count = created_count
        request._notification_bulk_scope = send_scope
        self.message_user(
            request,
            f"Создано уведомлений: {created_count}. Каждый пользователь получил свою отдельную запись.",
            level=messages.SUCCESS,
        )

    def response_add(self, request, obj, post_url_continue=None):
        if getattr(request, "_notification_bulk_count", None) is not None:
            return redirect(reverse("admin:notifications_notification_changelist"))
        return super().response_add(request, obj, post_url_continue)

    def _resolve_recipients(self, *, send_scope: str, form: NotificationAdminForm):
        base_queryset = User.objects.filter(is_deleted=False, is_active=True)
        if send_scope == NotificationAdminForm.SendScope.SELECTED:
            return form.cleaned_data["recipients"]
        if send_scope == NotificationAdminForm.SendScope.ALL_USERS:
            return base_queryset.order_by("email")
        if send_scope == NotificationAdminForm.SendScope.MOSQUE_ADMINS:
            return base_queryset.filter(role=User.Role.MOSQUE_ADMIN).order_by("email")
        if send_scope == NotificationAdminForm.SendScope.PLATFORM_ADMINS:
            return base_queryset.filter(role=User.Role.PLATFORM_ADMIN).order_by("email")
        return base_queryset.none()

    @display(description="Прочитано", label={"Прочитано": "success", "Не прочитано": "warning"})
    def is_read_badge(self, obj):
        return "Прочитано" if obj.is_read else "Не прочитано"

    @admin.action(description="Отметить выбранные как прочитанные")
    def mark_selected_read(self, request, queryset):
        now = timezone.now()
        queryset.update(is_read=True, read_at=now, updated_at=now)

    @admin.action(description="Отметить выбранные как непрочитанные")
    def mark_selected_unread(self, request, queryset):
        queryset.update(is_read=False, read_at=None, updated_at=timezone.now())
