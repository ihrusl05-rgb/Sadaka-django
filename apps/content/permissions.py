from rest_framework.permissions import SAFE_METHODS, BasePermission


class ContentAccessPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_platform_admin:
            return True
        if request.method in SAFE_METHODS:
            return obj.moderation_status == obj.ModerationStatus.APPROVED and obj.is_published and not obj.is_blocked
        if obj.mosque_id:
            return obj.mosque.memberships.filter(user=request.user).exists()
        return request.user.is_platform_admin
