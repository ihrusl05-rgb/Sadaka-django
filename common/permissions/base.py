from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_platform_admin)


class IsMosqueAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_mosque_admin)


class IsOwnerOrPlatformAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return bool(
            request.user
            and request.user.is_authenticated
            and (getattr(obj, "user_id", None) == request.user.id or request.user.is_platform_admin)
        )


class IsMosqueManagerOfObject(BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_platform_admin:
            return True
        mosque = getattr(obj, "mosque", None)
        if mosque is None and hasattr(obj, "project"):
            mosque = getattr(obj.project, "mosque", None)
        if mosque is None:
            return False
        return request.user.managed_mosques.filter(id=mosque.id).exists()


class ReadOnlyOrApprovedPublic(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return bool(
                getattr(obj, "moderation_status", None) in {"approved", None}
                and not getattr(obj, "is_blocked", False)
            )
        return bool(request.user and request.user.is_authenticated)


class CanModerateObject(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_platform_admin)
