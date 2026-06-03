from contextvars import ContextVar

_current_user: ContextVar = ContextVar("current_user", default=None)


def set_current_user(user) -> None:
    _current_user.set(user)


def get_current_user():
    return _current_user.get()


def clear_current_user() -> None:
    _current_user.set(None)
