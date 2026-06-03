from __future__ import annotations

import json
import logging
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)


class TelegramNotifyError(RuntimeError):
    pass


def send_telegram_message(
    *,
    bot_token: str,
    chat_ids: Iterable[int],
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    timeout: int = 10,
    reply_markup: dict | None = None,
) -> None:
    normalized_token = (bot_token or "").strip()
    if not normalized_token:
        raise TelegramNotifyError("Telegram bot token is not configured.")

    normalized_chat_ids = tuple(int(chat_id) for chat_id in chat_ids if chat_id)
    if not normalized_chat_ids:
        raise TelegramNotifyError("Telegram chat ids are not configured.")

    endpoint = f"https://api.telegram.org/bot{normalized_token}/sendMessage"
    errors: list[Exception] = []

    for chat_id in normalized_chat_ids:
        request_payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup:
            request_payload["reply_markup"] = reply_markup

        payload = json.dumps(request_payload).encode("utf-8")
        request = Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8") or "{}")
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.exception(
                "Telegram notification request failed",
                extra={"chat_id": chat_id},
            )
            errors.append(exc)
            continue

        if not response_payload.get("ok"):
            logger.error(
                "Telegram notification API rejected message",
                extra={"chat_id": chat_id, "response_ok": response_payload.get("ok")},
            )
            errors.append(TelegramNotifyError("Telegram API rejected message."))

    if errors and len(errors) == len(normalized_chat_ids):
        raise TelegramNotifyError("Unable to deliver Telegram notification.")
