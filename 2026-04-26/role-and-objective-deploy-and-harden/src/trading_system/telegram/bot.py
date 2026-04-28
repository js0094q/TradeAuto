from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file")
    parser.add_argument("--once-command")
    parser.add_argument("--once-chat-id")
    args = parser.parse_args()
    settings = load_settings(args.env_file)
    handler = TelegramCommandHandler(settings)

    if args.once_command and args.once_chat_id:
        message = handler.handle(args.once_chat_id, args.once_command)
        print(message.text)
        return 0

    print("telegram long polling is not enabled in this scaffold; use python-telegram-bot integration before production", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

