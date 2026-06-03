from apps.users.models import User


def get_users_for_actor(*, actor):
    if not getattr(actor, "is_authenticated", False):
        return User.objects.none()
    if getattr(actor, "is_platform_admin", False):
        return User.objects.all()
    return User.objects.filter(id=actor.id)
