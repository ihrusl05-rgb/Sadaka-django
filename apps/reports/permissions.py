from rest_framework.permissions import BasePermission


class ReportAccessPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_platform_admin:
            return True
        if request.user.is_mosque_admin and obj.mosque_id:
            return obj.mosque.memberships.filter(user=request.user).exists()
        return obj.requested_by_id == request.user.id
