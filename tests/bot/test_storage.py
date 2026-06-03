from unittest.mock import MagicMock

from bot.storage import (
    clear_support_admin_draft,
    get_support_admin_draft,
    set_support_admin_draft,
)


def test_support_admin_draft_stores_mapping_and_can_be_cleared():
    redis_client = MagicMock()

    set_support_admin_draft(
        redis_client,
        admin_telegram_id=100,
        ticket_id=200,
    )

    redis_client.hset.assert_called_once()
    redis_client.expire.assert_called_once()

    get_support_admin_draft(redis_client, admin_telegram_id=100)
    redis_client.hgetall.assert_called_once()

    clear_support_admin_draft(redis_client, admin_telegram_id=100)
    redis_client.delete.assert_called_once()
