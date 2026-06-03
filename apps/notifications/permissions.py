from rest_framework.permissions import BasePermission


class NotificationAccessPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if obj.user_id is None:
            return bool(request.user.is_platform_admin)
        return bool(request.user.is_platform_admin or obj.user_id == request.user.id)
