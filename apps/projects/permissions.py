from rest_framework.permissions import SAFE_METHODS, BasePermission


class ProjectAccessPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_platform_admin:
            return True
        if request.method in SAFE_METHODS:
            return obj.status in {obj.Status.APPROVED, obj.Status.ACTIVE} and not obj.is_blocked
        return obj.mosque.memberships.filter(user=request.user).exists()
