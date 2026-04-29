from __future__ import annotations

import argparse
import json
import logging
import signal
import time
from dataclasses import dataclass
from typing import Any

import requests

from trading_system.config import Settings, load_settings
from trading_system.health import health_payload, metrics_payload, readiness_payload
from trading_system.kill_switch import KillSwitch


@dataclass(frozen=True)
class TelegramMessage:
    chat_id: str
    text: str


class TelegramAuthorizer:
    def __init__(self, settings: Settings) -> None:
        self.allowed = set(settings.telegram_allowed_chat_ids)
        self.admins = set(settings.telegram_admin_chat_ids)

    def is_allowed(self, chat_id: str) -> bool:
        return chat_id in self.allowed or chat_id in self.admins

    def is_admin(self, chat_id: str) -> bool:
        return chat_id in self.admins


class TelegramCommandHandler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.authorizer = TelegramAuthorizer(settings)

    def handle(self, chat_id: str, command: str) -> TelegramMessage:
        if not self.authorizer.is_allowed(chat_id):
            return TelegramMessage(chat_id, "unauthorized")

        command_name = command.split()[0].lower()
        if command_name == "/status":
            return TelegramMessage(chat_id, json.dumps(metrics_payload(self.settings), sort_keys=True))
        if command_name == "/health":
            return TelegramMessage(chat_id, json.dumps(health_payload(), sort_keys=True))
        if command_name == "/ready":
            return TelegramMessage(chat_id, json.dumps(readiness_payload(self.settings, external=False), sort_keys=True))
        if command_name in {"/account", "/positions", "/orders", "/pnl", "/strategies", "/risk"}:
            return TelegramMessage(chat_id, f"{command_name[1:]} report is available through protected API/CLI diagnostics")
        if command_name == "/kill":
            if not self.authorizer.is_admin(chat_id):
                return TelegramMessage(chat_id, "admin required")
            KillSwitch(self.settings.kill_switch_file).enable()
            return TelegramMessage(chat_id, "kill switch enabled; new trading is blocked")
        if command_name == "/resume":
            if not self.authorizer.is_admin(chat_id):
                return TelegramMessage(chat_id, "admin required")
            ready = readiness_payload(self.settings, external=False)
            if not ready["ok"]:
                return TelegramMessage(chat_id, "resume blocked; readiness failed")
            KillSwitch(self.settings.kill_switch_file).disable()
            return TelegramMessage(chat_id, "kill switch disabled after readiness validation")
        return TelegramMessage(chat_id, "unknown command")


def send_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    response.raise_for_status()


def telegram_api_request(token: str, method: str, payload: dict[str, Any], *, timeout: int = 10) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed: {body.get('description', 'unknown error')}")
    return body


def get_updates(token: str, offset: int | None, *, timeout_seconds: int = 50) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {"timeout": timeout_seconds, "allowed_updates": ["message"]}
    if offset is not None:
        payload["offset"] = offset
    body = telegram_api_request(token, "getUpdates", payload, timeout=timeout_seconds + 10)
    result = body.get("result", [])
    if not isinstance(result, list):
        raise RuntimeError("Telegram API getUpdates returned an invalid result")
    return result


def message_from_update(handler: TelegramCommandHandler, update: dict[str, Any]) -> TelegramMessage | None:
    raw_message = update.get("message")
    if not isinstance(raw_message, dict):
        return None
    raw_chat = raw_message.get("chat")
    text = raw_message.get("text")
    if not isinstance(raw_chat, dict) or not isinstance(text, str) or not text.startswith("/"):
        return None
    chat_id = raw_chat.get("id")
    if chat_id is None:
        return None
    return handler.handle(str(chat_id), text)


def run_long_polling(settings: Settings) -> int:
    if not settings.telegram_bot_token:
        logging.error("TELEGRAM_BOT_TOKEN is required")
        return 2

    handler = TelegramCommandHandler(settings)
    running = True
    offset: int | None = None

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    telegram_api_request(settings.telegram_bot_token, "deleteWebhook", {"drop_pending_updates": True})
    logging.info("telegram long polling started")

    while running:
        try:
            for update in get_updates(settings.telegram_bot_token, offset):
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                message = message_from_update(handler, update)
                if message is not None:
                    send_message(settings.telegram_bot_token, message.chat_id, message.text)
        except requests.RequestException as exc:
            logging.warning("telegram request failed: %s", exc)
            time.sleep(5)

    logging.info("telegram long polling stopped")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file")
    parser.add_argument("--once-command")
    parser.add_argument("--once-chat-id")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings(args.env_file)
    handler = TelegramCommandHandler(settings)

    if args.once_command and args.once_chat_id:
        message = handler.handle(args.once_chat_id, args.once_command)
        print(message.text)
        return 0

    return run_long_polling(settings)


if __name__ == "__main__":
    raise SystemExit(main())
