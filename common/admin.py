from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline


def unfold_environment(request: HttpRequest):
    return ["LOCAL", "warning"] if settings.DEBUG else ["PROD", "success"]


def admin_link_for(obj, *, label: str | None = None):
    if not obj or not getattr(obj, "pk", None):
        return "-"
    url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
    return format_html('<a href="{}">{}</a>', url, label or str(obj))


class SadakaModelAdmin(UnfoldModelAdmin):
    compressed_fields = True
    list_filter_submit = True
    show_facets = admin.ShowFacets.NEVER
    warn_unsaved_form = True

    def notify_action(self, request: HttpRequest, message: str, *, level: int = messages.SUCCESS):
        self.message_user(request, message, level=level)

    def redirect_to_change(self, obj):
        return redirect(reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk]))

    def save_model(self, request, obj, form, change):
        for field_name in ("created_by", "author", "requested_by"):
            if hasattr(obj, field_name) and getattr(obj, f"{field_name}_id", None) is None:
                setattr(obj, field_name, request.user)
        super().save_model(request, obj, form, change)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield and db_field.name == "slug":
            formfield.help_text = "Слаг подставляется автоматически из названия и будет пересчитан при сохранении."
        return formfield

    def get_action_object(self, request, object_id, *, permission_check=None):
        obj = self.get_object(request, object_id)
        checker = permission_check or self.has_change_permission
        if not obj or not checker(request, obj):
            return None
        return obj

    def has_action_permission(self, request, object_id, *, permission_check=None):
        return bool(self.get_action_object(request, object_id, permission_check=permission_check))

    def has_platform_action_permission(self, request, object_id, *, permission_check=None):
        return bool(
            request.user.is_platform_admin
            and self.get_action_object(request, object_id, permission_check=permission_check)
        )


class PlatformOnlyAdminMixin:
    def has_module_permission(self, request):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_platform_admin
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


class MosqueScopedAdminMixin:
    restrict_user_fields = ()

    def has_module_permission(self, request):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_platform_admin or request.user.is_mosque_admin)
        )

    def has_view_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False
        if request.user.is_platform_admin or obj is None:
            return True
        return self._belongs_to_managed_mosque(request, obj)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def get_managed_mosques(self, request):
        from apps.mosques.models import Mosque

        return Mosque.objects.filter(memberships__user=request.user).distinct()

    def get_mosque_scope_q(self, request):
        return Q(mosque__memberships__user=request.user)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_platform_admin:
            return queryset
        if request.user.is_mosque_admin:
            return queryset.filter(self.get_mosque_scope_q(request)).distinct()
        return queryset.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if request.user.is_authenticated and request.user.is_mosque_admin:
            related_model = db_field.remote_field.model
            queryset = kwargs.get("queryset") or related_model._default_manager.all()

            if related_model._meta.label_lower == "mosques.mosque":
                kwargs["queryset"] = self.get_managed_mosques(request)
            elif related_model._meta.label_lower == "projects.project":
                kwargs["queryset"] = queryset.filter(mosque__in=self.get_managed_mosques(request)).distinct()
            elif related_model._meta.label_lower == "subscriptions.subscription":
                kwargs["queryset"] = queryset.filter(mosque__in=self.get_managed_mosques(request)).distinct()
            elif db_field.name in self.restrict_user_fields:
                kwargs["queryset"] = queryset.filter(pk=request.user.pk)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        managed = self.get_managed_mosques(request) if request.user.is_authenticated and request.user.is_mosque_admin else None

        for field_name in ("created_by", "author", "requested_by"):
            if field_name in {field.name for field in self.model._meta.fields}:
                initial.setdefault(field_name, request.user.pk)

        if managed is not None and managed.count() == 1 and "mosque" in {field.name for field in self.model._meta.fields}:
            initial.setdefault("mosque", managed.first().pk)

        return initial

    def _belongs_to_managed_mosque(self, request, obj):
        raise NotImplementedError


class MosqueScopedReadOnlyAdminMixin(MosqueScopedAdminMixin):
    def has_add_permission(self, request):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_platform_admin
        )

    def has_change_permission(self, request, obj=None):
        if not self.has_view_permission(request, obj):
            return False
        return bool(request.user.is_platform_admin)

    def has_delete_permission(self, request, obj=None):
        if not self.has_view_permission(request, obj):
            return False
        return bool(request.user.is_platform_admin)


ModelAdmin = SadakaModelAdmin
TabularInline = UnfoldTabularInline
