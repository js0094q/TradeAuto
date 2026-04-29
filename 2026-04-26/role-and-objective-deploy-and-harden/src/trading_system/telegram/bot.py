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
PAPER_STRATEGY_PATHS = ["/paper-strategy"]


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


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _summarize_paper_strategy(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "Paper strategy payload is unavailable."
    paper_execution = payload.get("paper_execution")
    strategy_items = payload.get("strategies")
    strategies = strategy_items if isinstance(strategy_items, list) else []
    execution = paper_execution if isinstance(paper_execution, dict) else {}
    orders = execution.get("orders") if isinstance(execution.get("orders"), list) else []
    submitted_buy = sum(1 for item in orders if isinstance(item, dict) and item.get("submitted") and item.get("side") == "buy")
    submitted_sell = sum(1 for item in orders if isinstance(item, dict) and item.get("submitted") and item.get("side") == "sell")
    selected = 0
    exits = 0
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        selected_items = strategy.get("selected")
        exit_items = strategy.get("exits")
        selected += len(selected_items) if isinstance(selected_items, list) else 0
        exits += len(exit_items) if isinstance(exit_items, list) else 0
    lines = [
        f"Paper status: {payload.get('status') or 'unknown'}",
        f"Cycle timestamp: {payload.get('timestamp') or 'unknown'}",
        f"Execution status: {execution.get('status') or 'unknown'}",
        f"Strategies: {len(strategies)} | Selected: {selected} | Exit intents: {exits}",
        f"Submitted buys: {submitted_buy} | Submitted sells: {submitted_sell}",
    ]
    runtime_blocks = execution.get("runtime_gate_blocks")
    if isinstance(runtime_blocks, list) and runtime_blocks:
        lines.append("Runtime gate blocks: " + ", ".join(str(item) for item in runtime_blocks[:4]))
    return "\n".join(lines)


def _summarize_paper_orders(payload: Any, *, max_items: int = 8) -> str:
    if not isinstance(payload, dict):
        return "Paper strategy payload is unavailable."
    paper_execution = payload.get("paper_execution")
    if not isinstance(paper_execution, dict):
        return "Paper execution payload is unavailable."
    orders = paper_execution.get("orders")
    if not isinstance(orders, list) or not orders:
        return f"Paper execution status: {paper_execution.get('status') or 'unknown'}. No order rows in latest cycle."
    lines = [f"Paper execution: {paper_execution.get('status') or 'unknown'}", f"Latest order rows ({len(orders)}):"]
    for order in orders[:max_items]:
        if not isinstance(order, dict):
            continue
        side = str(order.get("side") or "unknown").upper()
        symbol = str(order.get("symbol") or "UNKNOWN")
        status = str(order.get("status") or "unknown")
        qty = _float_or_none(order.get("qty"))
        notional = _float_or_none(order.get("notional_usd"))
        target = _float_or_none(order.get("target_notional_usd"))
        current = _float_or_none(order.get("current_position_notional_usd"))
        details: list[str] = []
        if qty is not None:
            details.append(f"qty={qty:.4f}")
        if notional is not None:
            details.append(f"order=${notional:.2f}")
        if side == "BUY" and target is not None:
            details.append(f"target=${target:.2f}")
        if current is not None:
            details.append(f"current=${current:.2f}")
        if order.get("error"):
            details.append("error_present")
        lines.append(f"- {side} {symbol}: {status}" + (f" ({', '.join(details)})" if details else ""))
    if len(orders) > max_items:
        lines.append(f"...and {len(orders) - max_items} more")
    lookup_error = paper_execution.get("position_lookup_error")
    if isinstance(lookup_error, str) and lookup_error:
        lines.append(f"Position lookup error: {lookup_error}")
    return "\n".join(lines)


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
            "/paper\n"
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


async def paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return
    path, body = await _api_get(PAPER_STRATEGY_PATHS)
    if update.message:
        await update.message.reply_text(f"Paper strategy endpoint: {path}\n{_summarize_paper_strategy(body)}")


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

    path, body = await _api_get(PAPER_STRATEGY_PATHS)
    if update.message:
        await update.message.reply_text(f"Paper orders endpoint: {path}\n{_summarize_paper_orders(body)}")


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
    application.add_handler(CommandHandler("paper", paper))
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
