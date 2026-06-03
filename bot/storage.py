from __future__ import annotations

from datetime import datetime, timezone

from redis import Redis

from bot.settings import BotSettings, JOB_TTL_SECONDS


SUPPORT_ADMIN_DRAFT_PREFIX = "bot:support:admin-draft"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_redis_client(settings: BotSettings) -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def support_admin_draft_key(admin_telegram_id: int) -> str:
    return f"{SUPPORT_ADMIN_DRAFT_PREFIX}:{admin_telegram_id}"


def set_support_admin_draft(
    redis_client: Redis,
    *,
    admin_telegram_id: int,
    ticket_id: int,
) -> None:
    key = support_admin_draft_key(admin_telegram_id)
    redis_client.hset(
        key,
        mapping={
            "ticket_id": str(ticket_id),
            "created_at": utcnow_iso(),
        },
    )
    redis_client.expire(key, JOB_TTL_SECONDS)


def get_support_admin_draft(redis_client: Redis, *, admin_telegram_id: int) -> dict[str, str]:
    return redis_client.hgetall(support_admin_draft_key(admin_telegram_id))


def clear_support_admin_draft(redis_client: Redis, *, admin_telegram_id: int) -> None:
    redis_client.delete(support_admin_draft_key(admin_telegram_id))
