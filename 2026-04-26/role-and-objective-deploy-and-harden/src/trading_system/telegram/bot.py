from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("trading_system.telegram.bot")

# Telegram request URLs contain the bot token. Keep transport libraries out of INFO logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO)

HEALTH_PATHS = ["/health"]
STATUS_PATHS = ["/ready", "/metrics", "/health"]
KILL_SWITCH_PATHS = ["/admin/kill"]


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _chat_ids(name: str, *, required: bool) -> set[int]:
    raw = os.getenv(name, "").strip()
    if required and not raw:
        raise RuntimeError(f"{name} is required")

    ids: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if item:
            ids.add(int(item))

    if required and not ids:
        raise RuntimeError(f"{name} must contain at least one chat id")
    return ids


def _allowed_chat_ids() -> set[int]:
    return _chat_ids("TELEGRAM_ALLOWED_CHAT_IDS", required=True)


def _admin_chat_ids() -> set[int]:
    return _chat_ids("TELEGRAM_ADMIN_CHAT_IDS", required=False)


def _api_base_url() -> str:
    return (
        os.getenv("TRADING_API_BASE_URL")
        or os.getenv("CONTROL_API_BASE_URL")
        or os.getenv("API_BASE_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _api_headers() -> dict[str, str]:
    token = (
        os.getenv("TRADING_SYSTEM_CONTROL_PLANE_TOKEN")
        or os.getenv("CONTROL_API_TOKEN")
        or os.getenv("ADMIN_TOKEN")
        or ""
    ).strip()

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Admin-Token"] = token
        headers["X-Control-Token"] = token
    return headers


def _format_payload(payload: Any) -> str:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, indent=2, sort_keys=True, default=str)

    if len(text) > 3500:
        text = text[:3500] + "\n...[truncated]"

    return f"```json\n{text}\n```"


async def _api_get(paths: list[str]) -> tuple[str, Any]:
    base = _api_base_url()
    headers = _api_headers()

    async with httpx.AsyncClient(timeout=10.0) as client:
        last_error: Any = None

        for path in paths:
            url = f"{base}{path}"
            try:
                response = await client.get(url, headers=headers)
                content_type = response.headers.get("content-type", "")
                body: Any = response.json() if "application/json" in content_type else response.text

                if response.status_code < 400:
                    return path, body

                last_error = {
                    "path": path,
                    "status_code": response.status_code,
                    "body": body,
                }
            except Exception as exc:
                last_error = {"path": path, "error": str(exc)}

    return "none", {"error": "all candidate API paths failed", "last_error": last_error}


async def _api_post(paths: list[str], payload: dict[str, Any] | None = None) -> tuple[str, Any]:
    base = _api_base_url()
    headers = _api_headers()

    async with httpx.AsyncClient(timeout=10.0) as client:
        last_error: Any = None

        for path in paths:
            url = f"{base}{path}"
            try:
                response = await client.post(url, headers=headers, json=payload or {})
                content_type = response.headers.get("content-type", "")
                body: Any = response.json() if "application/json" in content_type else response.text

                if response.status_code < 400:
                    return path, body

                last_error = {
                    "path": path,
                    "status_code": response.status_code,
                    "body": body,
                }
            except Exception as exc:
                last_error = {"path": path, "error": str(exc)}

    return "none", {"error": "all candidate API paths failed", "last_error": last_error}


async def _authorized(update: Update) -> bool:
    if not update.effective_chat:
        return False

    allowed = _allowed_chat_ids()
    chat_id = update.effective_chat.id

    if chat_id not in allowed:
        logger.warning("Rejected unauthorized Telegram chat_id=%s", chat_id)
        if update.message:
            await update.message.reply_text("Unauthorized chat.")
        return False

    return True


async def _admin_authorized(update: Update) -> bool:
    if not await _authorized(update):
        return False

    admins = _admin_chat_ids()
    chat_id = update.effective_chat.id if update.effective_chat else None
    if admins and chat_id not in admins:
        logger.warning("Rejected non-admin Telegram chat_id=%s", chat_id)
        if update.message:
            await update.message.reply_text("Admin chat required.")
        return False

    return True


async def _reply_json(update: Update, title: str, path: str, body: Any) -> None:
    if update.message:
        await update.message.reply_text(
            f"{title} endpoint: {path}\n{_format_payload(body)}",
            parse_mode=ParseMode.MARKDOWN,
        )


async def _reply_unavailable(update: Update, label: str) -> None:
    if update.message:
        await update.message.reply_text(
            f"{label} is not exposed by this API yet. Use protected API/CLI diagnostics on the VPS."
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return

    if update.message:
        await update.message.reply_text(
            "Trading Telegram bot online.\n\n"
            "Available commands:\n"
            "/health\n"
            "/status\n"
            "/account\n"
            "/positions\n"
            "/orders\n"
            "/kill\n\n"
            "No order-placement commands are enabled in this bot."
        )


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return

    path, body = await _api_get(HEALTH_PATHS)
    await _reply_json(update, "Health", path, body)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return

    path, body = await _api_get(STATUS_PATHS)
    await _reply_json(update, "Status", path, body)


async def account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return

    await _reply_unavailable(update, "Account report")


async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return

    await _reply_unavailable(update, "Positions report")


async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return

    await _reply_unavailable(update, "Orders report")


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_authorized(update):
        return

    path, body = await _api_post(KILL_SWITCH_PATHS)
    await _reply_json(update, "Kill-switch", path, body)


def main() -> None:
    token = _required_env("TELEGRAM_BOT_TOKEN")
    _allowed_chat_ids()

    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("health", health))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("account", account))
    application.add_handler(CommandHandler("positions", positions))
    application.add_handler(CommandHandler("orders", orders))
    application.add_handler(CommandHandler("kill", kill))

    logger.info("Starting Telegram long polling")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
