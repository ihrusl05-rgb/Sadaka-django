from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import urlparse, urlunparse

import environ


ROOT_DIR: Final[Path] = Path(__file__).resolve().parent.parent
ENV_FILE: Final[Path] = ROOT_DIR / ".env"
DEFAULT_LOG_DIR: Final[Path] = ROOT_DIR / "var" / "bot" / "logs"
JOB_TTL_SECONDS: Final[int] = 60 * 60 * 24 * 7
TELEGRAM_MESSAGE_LIMIT: Final[int] = 3500

env = environ.Env(
    REDIS_URL=(str, "redis://127.0.0.1:6379/0"),
    TELEGRAM_AUTH_BOT_TOKEN=(str, ""),
    TELEGRAM_AUTH_BOT_USERNAME=(str, ""),
    TELEGRAM_SUPPORT_BOT_TOKEN=(str, ""),
    SUPPORT_ADMIN_IDS=(str, ""),
    TELEGRAM_SUPPORT_ADMIN_USER_IDS=(str, ""),
    TELEGRAM_SUPPORT_USERNAME=(str, ""),
    TELEGRAM_PARTNERSHIP_USERNAME=(str, ""),
    APP_BASE_URL=(str, "http://127.0.0.1:8000"),
    BOT_LOG_DIR=(str, str(DEFAULT_LOG_DIR)),
    BOT_REDIS_DB=(int, 1),
)
environ.Env.read_env(ENV_FILE)


def _parse_csv_ints(raw: str) -> tuple[int, ...]:
    values = []
    for part in raw.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        values.append(int(stripped))
    return tuple(values)


def _with_redis_db(url: str, db: int) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise ValueError("REDIS_URL must use redis:// or rediss://")
    return urlunparse(parsed._replace(path=f"/{db}"))


@dataclass(frozen=True)
class BotSettings:
    redis_url: str
    telegram_bot_token: str
    telegram_bot_username: str
    telegram_allowed_user_ids: tuple[int, ...]
    telegram_support_username: str
    telegram_partnership_username: str
    app_base_url: str
    log_dir: Path

    @property
    def auth_bot_log_file(self) -> Path:
        return self.log_dir / "telegram-auth-bot.log"

    @property
    def support_bot_log_file(self) -> Path:
        return self.log_dir / "telegram-support-bot.log"


def _resolve_log_dir() -> Path:
    log_dir = Path(env("BOT_LOG_DIR")).expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _build_settings(
    *,
    token: str,
    username: str,
    allowed_user_ids: tuple[int, ...],
) -> BotSettings:
    return BotSettings(
        redis_url=_with_redis_db(env("REDIS_URL"), env.int("BOT_REDIS_DB")),
        telegram_bot_token=token,
        telegram_bot_username=username,
        telegram_allowed_user_ids=allowed_user_ids,
        telegram_support_username=env("TELEGRAM_SUPPORT_USERNAME").strip().lstrip("@"),
        telegram_partnership_username=env("TELEGRAM_PARTNERSHIP_USERNAME").strip().lstrip("@"),
        app_base_url=env("APP_BASE_URL").strip().rstrip("/"),
        log_dir=_resolve_log_dir(),
    )


def load_auth_bot_settings() -> BotSettings:
    token = env("TELEGRAM_AUTH_BOT_TOKEN").strip()
    if not token:
        raise RuntimeError("TELEGRAM_AUTH_BOT_TOKEN is required for the auth bot")

    return _build_settings(
        token=token,
        username=env("TELEGRAM_AUTH_BOT_USERNAME").strip().lstrip("@"),
        allowed_user_ids=(),
    )


def load_support_bot_settings() -> BotSettings:
    token = env("TELEGRAM_SUPPORT_BOT_TOKEN").strip()
    if not token:
        raise RuntimeError("TELEGRAM_SUPPORT_BOT_TOKEN is required for the support bot")
    username = env("TELEGRAM_SUPPORT_USERNAME").strip().lstrip("@")
    if not username:
        raise RuntimeError("TELEGRAM_SUPPORT_USERNAME is required for the support bot")

    admin_ids_raw = env("SUPPORT_ADMIN_IDS").strip() or env("TELEGRAM_SUPPORT_ADMIN_USER_IDS").strip()

    return _build_settings(
        token=token,
        username=username,
        allowed_user_ids=_parse_csv_ints(admin_ids_raw),
    )


def configure_logging(log_file: Path | None = None) -> None:
    target_log_file = log_file or (DEFAULT_LOG_DIR / "bot.log")
    target_log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
    )

    file_handler = logging.FileHandler(target_log_file)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
