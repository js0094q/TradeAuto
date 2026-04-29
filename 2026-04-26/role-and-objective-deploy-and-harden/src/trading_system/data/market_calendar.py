from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
EQUITY_OPEN = time(9, 30)
EQUITY_CLOSE = time(16, 0)


@dataclass(frozen=True)
class SessionState:
    asset_class: str
    is_open: bool
    session: str
    reason: str


def _eastern(moment: datetime | None = None) -> datetime:
    value = moment or datetime.now(tz=UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(EASTERN)


def is_equity_market_open(moment: datetime | None = None) -> bool:
    local = _eastern(moment)
    if local.weekday() >= 5:
        return False
    return EQUITY_OPEN <= local.time() < EQUITY_CLOSE


def session_state(asset_class: str, moment: datetime | None = None) -> SessionState:
    normalized = asset_class.strip().lower()
    local = _eastern(moment)
    if normalized == "crypto":
        return SessionState(normalized, True, "24_7", "crypto trades continuously; monitor liquidity separately")
    if normalized in {"equity", "etf", "option", "options"}:
        open_now = is_equity_market_open(local)
        if local.weekday() >= 5:
            reason = "weekend"
        elif local.time() < EQUITY_OPEN:
            reason = "before regular session"
        elif local.time() >= EQUITY_CLOSE:
            reason = "after regular session"
        else:
            reason = "regular session"
        return SessionState(normalized, open_now, "us_regular", reason)
    return SessionState(normalized, False, "unknown", "unsupported asset class")

