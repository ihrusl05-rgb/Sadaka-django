from rest_framework.permissions import SAFE_METHODS, BasePermission


class DonationAccessPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_platform_admin:
            return True
        if request.user.is_mosque_admin:
            return obj.mosque.memberships.filter(user=request.user).exists()
        return obj.user_id == request.user.id
