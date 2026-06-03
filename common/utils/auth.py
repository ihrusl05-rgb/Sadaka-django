from types import SimpleNamespace


def get_actor_or_anonymous(user):
    if getattr(user, "is_authenticated", False):
        return user
    return SimpleNamespace(is_authenticated=False, is_platform_admin=False, is_mosque_admin=False)
