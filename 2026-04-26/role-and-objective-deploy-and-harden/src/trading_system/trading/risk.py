from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from trading_system.config import RiskLimits


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    order_type: str
    limit_price: float | None
    asset_class: str = "equity"
    notional_usd: float | None = None

    def estimated_notional(self) -> float:
        if self.notional_usd is not None:
            return self.notional_usd
        if self.limit_price is None:
            return 0.0
        return abs(self.quantity * self.limit_price)


@dataclass(frozen=True)
class AccountState:
    buying_power: float
    daily_pnl: float = 0.0
    total_drawdown: float = 0.0
    open_positions: int = 0
    trades_today: int = 0
    market_is_open: bool = False


@dataclass(frozen=True)
class MarketState:
    asset_tradable: bool = True
    spread_pct: float | None = None
    volume: int | None = None
    min_volume: int | None = None


@dataclass(frozen=True)
class RiskState:
    kill_switch_enabled: bool
    duplicate_order_symbols: frozenset[str] = field(default_factory=frozenset)
    cooldown_symbols: frozenset[str] = field(default_factory=frozenset)
    consecutive_losses: int = 0
    max_consecutive_losses: int | None = None


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...] = ()


class RiskEngine:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def evaluate(
        self,
        order: OrderRequest,
        account: AccountState,
        market: MarketState,
        state: RiskState,
    ) -> RiskDecision:
        reasons: list[str] = []
        notional = order.estimated_notional()

        if state.kill_switch_enabled:
            reasons.append("kill switch is enabled")
        if not account.market_is_open:
            reasons.append("market is not open")
        if not market.asset_tradable:
            reasons.append("asset is not tradable")
        if self.limits.require_limit_orders and order.order_type != "limit":
            reasons.append("limit orders are required")
        if order.order_type == "market" and not self.limits.allow_market_orders:
            reasons.append("market orders are disabled")
        if order.side.lower() == "sell_short" and not self.limits.allow_short_selling:
            reasons.append("short selling is disabled")
        if order.asset_class == "option" and not self.limits.allow_options_trading:
            reasons.append("options trading is disabled")
        if order.asset_class == "crypto" and not self.limits.allow_crypto_trading:
            reasons.append("crypto trading is disabled")
        if self.limits.max_trades_per_day is not None:
            if account.trades_today >= self.limits.max_trades_per_day:
                reasons.append("max trades per day reached")
        if self.limits.max_open_positions is not None:
            if account.open_positions >= self.limits.max_open_positions:
                reasons.append("max open positions reached")
        if self.limits.max_order_notional_usd is not None:
            if notional <= 0:
                reasons.append("order notional must be positive and known")
            elif notional > self.limits.max_order_notional_usd:
                reasons.append("order notional exceeds limit")
        if self.limits.max_position_notional_usd is not None:
            if notional > self.limits.max_position_notional_usd:
                reasons.append("position notional exceeds limit")
        if account.buying_power < notional:
            reasons.append("insufficient buying power")
        if self.limits.max_daily_loss_usd is not None:
            if account.daily_pnl <= -abs(self.limits.max_daily_loss_usd):
                reasons.append("max daily loss reached")
        if self.limits.max_total_drawdown_usd is not None:
            if account.total_drawdown >= abs(self.limits.max_total_drawdown_usd):
                reasons.append("max total drawdown reached")
        if market.min_volume is not None and market.volume is not None:
            if market.volume < market.min_volume:
                reasons.append("volume below minimum")
        if market.spread_pct is not None and market.spread_pct > 1.0:
            reasons.append("spread exceeds maximum")
        if order.symbol in state.duplicate_order_symbols:
            reasons.append("duplicate order prevention triggered")
        if order.symbol in state.cooldown_symbols:
            reasons.append("symbol is in cooldown after loss")
        if state.max_consecutive_losses is not None:
            if state.consecutive_losses >= state.max_consecutive_losses:
                reasons.append("consecutive loss lockout triggered")

        return RiskDecision(approved=not reasons, reasons=tuple(reasons))


def material_rejection(reasons: Iterable[str]) -> bool:
    material = {"kill switch is enabled", "max daily loss reached", "max total drawdown reached"}
    return any(reason in material for reason in reasons)

