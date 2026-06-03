from django.contrib import admin

from apps.support.models import SupportMessage, SupportTicket, SupportUser


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    fields = ("sender_type", "sender_username", "text", "created_at")
    readonly_fields = ("sender_type", "sender_username", "text", "created_at")
    can_delete = False


@admin.register(SupportUser)
class SupportUserAdmin(admin.ModelAdmin):
    list_display = ("telegram_user_id", "username", "first_name", "last_name", "is_blocked", "first_seen_at", "last_seen_at")
    search_fields = ("telegram_user_id", "username", "first_name", "last_name")
    list_filter = ("is_blocked",)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "telegram_user_id", "username", "status", "assigned_admin_username", "created_at", "updated_at", "closed_at")
    search_fields = ("id", "telegram_user_id", "username", "first_name", "last_name", "assigned_admin_username")
    list_filter = ("status",)
    inlines = [SupportMessageInline]


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "sender_type", "sender_username", "created_at")
    search_fields = ("ticket__id", "sender_username", "text")
    list_filter = ("sender_type",)

