from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


LIVE_BASE_URL = "https://api.alpaca.markets"
PAPER_BASE_URL = "https://paper-api.alpaca.markets"


def default_shared_dir() -> Path:
    explicit = os.environ.get("TRADING_SYSTEM_SHARED_DIR", "").strip()
    if explicit:
        return Path(explicit)
    vps_path = Path("/opt/trading-system/shared")
    if vps_path.exists():
        return vps_path
    project_root = Path(__file__).resolve().parents[2]
    return project_root / ".runtime" / "shared"


def load_env_file(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"env file not found: {env_path}")
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_int(name: str, values: Mapping[str, str], default: int | None = None) -> int | None:
    value = values.get(name)
    if value in (None, ""):
        return default
    return int(value)


def parse_float(name: str, values: Mapping[str, str], default: float | None = None) -> float | None:
    value = values.get(name)
    if value in (None, ""):
        return default
    return float(value)


@dataclass(frozen=True)
class RiskLimits:
    max_trades_per_day: int | None
    max_open_positions: int | None
    max_order_notional_usd: float | None
    max_position_notional_usd: float | None
    max_daily_loss_usd: float | None
    max_total_drawdown_usd: float | None
    max_account_risk_pct: float | None
    require_limit_orders: bool = True
    allow_market_orders: bool = False
    allow_short_selling: bool = False
    allow_options_trading: bool = False
    allow_crypto_trading: bool = False

    def missing_fields(self) -> list[str]:
        required = {
            "MAX_TRADES_PER_DAY": self.max_trades_per_day,
            "MAX_OPEN_POSITIONS": self.max_open_positions,
            "MAX_ORDER_NOTIONAL_USD": self.max_order_notional_usd,
            "MAX_POSITION_NOTIONAL_USD": self.max_position_notional_usd,
            "MAX_DAILY_LOSS_USD": self.max_daily_loss_usd,
            "MAX_TOTAL_DRAWDOWN_USD": self.max_total_drawdown_usd,
            "MAX_ACCOUNT_RISK_PCT": self.max_account_risk_pct,
        }
        return [name for name, value in required.items() if value is None]


@dataclass(frozen=True)
class Settings:
    app_env: str
    trading_mode: str
    live_trading_enabled: bool
    host: str
    port: int
    postgres_url: str
    redis_url: str
    alpaca_api_key: str
    alpaca_api_secret: str
    alpaca_base_url: str
    alpaca_data_feed: str
    alpaca_cli_enabled: bool
    alpaca_cli_profile: str
    telegram_bot_token: str
    telegram_allowed_chat_ids: tuple[str, ...]
    telegram_admin_chat_ids: tuple[str, ...]
    jwt_signing_key: str
    admin_token: str
    dashboard_token: str
    log_level: str
    kill_switch_enabled: bool
    kill_switch_file: Path
    health_checks_enabled: bool
    risk: RiskLimits
    raw: Mapping[str, str] = field(repr=False)

    @property
    def is_live(self) -> bool:
        return self.trading_mode == "live"

    @property
    def is_paper(self) -> bool:
        return self.trading_mode == "paper"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise RuntimeError("startup validation failed: " + "; ".join(self.errors))


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def build_settings(values: Mapping[str, str]) -> Settings:
    normalized_values = dict(values)
    shared_dir = normalized_values.get("TRADING_SYSTEM_SHARED_DIR", "").strip()
    if not shared_dir:
        shared_dir = str(default_shared_dir())
        normalized_values["TRADING_SYSTEM_SHARED_DIR"] = shared_dir

    log_dir = normalized_values.get("LOG_DIR", "").strip()
    if not log_dir:
        log_dir = str(Path(shared_dir) / "logs")
        normalized_values["LOG_DIR"] = log_dir

    kill_switch_file = normalized_values.get("KILL_SWITCH_FILE", "").strip()
    if not kill_switch_file:
        kill_switch_file = str(Path(shared_dir) / "state" / "kill_switch.enabled")
        normalized_values["KILL_SWITCH_FILE"] = kill_switch_file

    allowed_chat_ids = normalized_values.get("TELEGRAM_ALLOWED_CHAT_IDS")
    if allowed_chat_ids is None:
        allowed_chat_ids = normalized_values.get("CHAT_IDS", "")
    admin_chat_ids = normalized_values.get("TELEGRAM_ADMIN_CHAT_IDS")
    if admin_chat_ids is None:
        admin_chat_ids = normalized_values.get("ADMIN_CHAT_IDS", "")

    risk = RiskLimits(
        max_trades_per_day=parse_int("MAX_TRADES_PER_DAY", normalized_values),
        max_open_positions=parse_int("MAX_OPEN_POSITIONS", normalized_values),
        max_order_notional_usd=parse_float("MAX_ORDER_NOTIONAL_USD", normalized_values),
        max_position_notional_usd=parse_float("MAX_POSITION_NOTIONAL_USD", normalized_values),
        max_daily_loss_usd=parse_float("MAX_DAILY_LOSS_USD", normalized_values),
        max_total_drawdown_usd=parse_float("MAX_TOTAL_DRAWDOWN_USD", normalized_values),
        max_account_risk_pct=parse_float("MAX_ACCOUNT_RISK_PCT", normalized_values),
        require_limit_orders=parse_bool(normalized_values.get("REQUIRE_LIMIT_ORDERS", "true")),
        allow_market_orders=parse_bool(normalized_values.get("ALLOW_MARKET_ORDERS", "false")),
        allow_short_selling=parse_bool(normalized_values.get("ALLOW_SHORT_SELLING", "false")),
        allow_options_trading=parse_bool(normalized_values.get("ALLOW_OPTIONS_TRADING", "false")),
        allow_crypto_trading=parse_bool(normalized_values.get("ALLOW_CRYPTO_TRADING", "false")),
    )
    return Settings(
        app_env=normalized_values.get("APP_ENV", "").strip(),
        trading_mode=normalized_values.get("TRADING_MODE", "").strip(),
        live_trading_enabled=parse_bool(normalized_values.get("LIVE_TRADING_ENABLED", "false")),
        host=normalized_values.get("HOST", "127.0.0.1").strip(),
        port=int(normalized_values.get("PORT", "8000")),
        postgres_url=normalized_values.get("POSTGRES_URL", "").strip(),
        redis_url=normalized_values.get("REDIS_URL", "").strip(),
        alpaca_api_key=normalized_values.get("ALPACA_API_KEY", "").strip(),
        alpaca_api_secret=normalized_values.get("ALPACA_API_SECRET", "").strip(),
        alpaca_base_url=normalized_values.get("ALPACA_BASE_URL", "").strip(),
        alpaca_data_feed=normalized_values.get("ALPACA_DATA_FEED", "iex").strip(),
        alpaca_cli_enabled=parse_bool(normalized_values.get("ALPACA_CLI_ENABLED", "false")),
        alpaca_cli_profile=normalized_values.get("ALPACA_CLI_PROFILE", "").strip(),
        telegram_bot_token=normalized_values.get("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_allowed_chat_ids=_split_csv(allowed_chat_ids),
        telegram_admin_chat_ids=_split_csv(admin_chat_ids),
        jwt_signing_key=normalized_values.get("JWT_SIGNING_KEY", "").strip(),
        admin_token=normalized_values.get("ADMIN_TOKEN", "").strip(),
        dashboard_token=normalized_values.get("DASHBOARD_TOKEN", "").strip(),
        log_level=normalized_values.get("LOG_LEVEL", "INFO").strip(),
        kill_switch_enabled=parse_bool(normalized_values.get("KILL_SWITCH_ENABLED", "false")),
        kill_switch_file=Path(kill_switch_file),
        health_checks_enabled=parse_bool(normalized_values.get("HEALTH_CHECKS_ENABLED", "true")),
        risk=risk,
        raw=normalized_values,
    )


def load_settings(env_file: str | Path | None = None) -> Settings:
    resolved_env_file = env_file
    if resolved_env_file is None:
        override = os.environ.get("TRADING_SYSTEM_ENV_FILE", "").strip()
        if override:
            resolved_env_file = override
        elif not os.environ.get("TRADING_MODE", "").strip():
            for candidate in (".env.runtime", ".env.test", ".env.paper", ".env.test.example"):
                if Path(candidate).exists():
                    resolved_env_file = candidate
                    break

    loaded = load_env_file(resolved_env_file)
    merged = dict(os.environ)
    merged.update(loaded)
    return build_settings(merged)


def validate_settings(settings: Settings, *, mode: str | None = None) -> ValidationResult:
    target_mode = mode or settings.trading_mode
    errors: list[str] = []
    warnings: list[str] = []

    if target_mode not in {"diagnostics", "paper", "test", "live"}:
        errors.append("TRADING_MODE must be diagnostics, paper, test, or live")

    if settings.host != "127.0.0.1":
        errors.append("HOST must be 127.0.0.1; only Nginx may bind publicly")

    if not settings.health_checks_enabled:
        errors.append("HEALTH_CHECKS_ENABLED must be true")

    if not settings.postgres_url:
        errors.append("POSTGRES_URL is required")
    elif "127.0.0.1" not in settings.postgres_url and "localhost" not in settings.postgres_url:
        errors.append("POSTGRES_URL must point to localhost")

    if settings.redis_url and "127.0.0.1" not in settings.redis_url and "localhost" not in settings.redis_url:
        errors.append("REDIS_URL must point to localhost")

    if not settings.admin_token or settings.admin_token == "CHANGE_ME":
        errors.append("ADMIN_TOKEN must be set to a real secret")
    if not settings.dashboard_token or settings.dashboard_token == "CHANGE_ME":
        errors.append("DASHBOARD_TOKEN must be set to a real secret")

    missing_risk = settings.risk.missing_fields()
    if missing_risk:
        errors.append("missing risk limits: " + ", ".join(missing_risk))

    if settings.risk.max_order_notional_usd is not None and settings.risk.max_order_notional_usd <= 0:
        errors.append("MAX_ORDER_NOTIONAL_USD must be positive")
    if settings.risk.max_daily_loss_usd is not None and settings.risk.max_daily_loss_usd <= 0:
        errors.append("MAX_DAILY_LOSS_USD must be positive")

    if target_mode == "live":
        if settings.trading_mode != "live":
            errors.append("TRADING_MODE must be exactly live for live startup")
        if not settings.live_trading_enabled:
            errors.append("LIVE_TRADING_ENABLED must be exactly true for live startup")
        if settings.alpaca_base_url != LIVE_BASE_URL:
            errors.append("live mode must use https://api.alpaca.markets")
        if not settings.alpaca_api_key or settings.alpaca_api_key == "CHANGE_ME":
            errors.append("ALPACA_API_KEY must be set for live startup")
        if not settings.alpaca_api_secret or settings.alpaca_api_secret == "CHANGE_ME":
            errors.append("ALPACA_API_SECRET must be set for live startup")
        expected_account_number = settings.raw.get("ALPACA_EXPECTED_ACCOUNT_NUMBER", "").strip()
        if not expected_account_number or expected_account_number == "CHANGE_ME":
            errors.append("ALPACA_EXPECTED_ACCOUNT_NUMBER must be set for live startup")
        if not settings.telegram_bot_token or settings.telegram_bot_token == "CHANGE_ME":
            errors.append("TELEGRAM_BOT_TOKEN must be set for live startup")
        if not settings.telegram_admin_chat_ids or "CHANGE_ME" in settings.telegram_admin_chat_ids:
            errors.append("TELEGRAM_ADMIN_CHAT_IDS must include at least one real admin chat ID")
        if not settings.kill_switch_file.exists():
            errors.append(f"kill switch file is not readable: {settings.kill_switch_file}")
        elif not os.access(settings.kill_switch_file, os.R_OK):
            errors.append(f"kill switch file is not readable: {settings.kill_switch_file}")
        if not settings.risk.require_limit_orders:
            errors.append("REQUIRE_LIMIT_ORDERS must be true for live startup")
        if settings.risk.allow_market_orders:
            warnings.append("ALLOW_MARKET_ORDERS is true; keep disabled unless explicitly approved")
    else:
        if settings.alpaca_base_url == LIVE_BASE_URL and settings.trading_mode != "live":
            errors.append("non-live modes must not point to the live Alpaca endpoint")
        if settings.live_trading_enabled:
            errors.append("LIVE_TRADING_ENABLED must be false outside live mode")

    if settings.trading_mode == "paper" and settings.alpaca_base_url != PAPER_BASE_URL:
        errors.append("paper mode must use https://paper-api.alpaca.markets")

    return ValidationResult(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))
