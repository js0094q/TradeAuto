from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from trading_system.config import RiskLimits
from trading_system.trading.order_intents import OrderIntent


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


@dataclass(frozen=True)
class ExecutionGateState:
    profile: str = "paper"
    enable_live_trading: bool = False
    allow_live_orders: bool = False
    broker_account_valid: bool = False
    strategy_live_enabled: bool = False


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

    def evaluate_intent(
        self,
        intent: OrderIntent,
        account: AccountState,
        market: MarketState,
        state: RiskState,
        *,
        execution: ExecutionGateState | None = None,
        order_type: str = "limit",
        limit_price: float | None = None,
        asset_class: str = "equity",
    ) -> OrderIntent:
        gate = execution or ExecutionGateState()
        reasons: list[str] = []

        if intent.mode == "live":
            if gate.profile != "live":
                reasons.append("live profile is required")
            if not gate.allow_live_orders:
                reasons.append("strategy live orders are disabled")
            if not gate.enable_live_trading:
                reasons.append("ENABLE_LIVE_TRADING must be true")
            if not gate.broker_account_valid:
                reasons.append("broker account is not validated")
            if not gate.strategy_live_enabled:
                reasons.append("strategy is not enabled for live")
        elif gate.profile == "live" and gate.enable_live_trading:
            reasons.append("paper intent cannot run under live execution gate")

        risk_state = state
        if state.kill_switch_enabled and not intent.adds_risk:
            risk_state = RiskState(
                kill_switch_enabled=False,
                duplicate_order_symbols=state.duplicate_order_symbols,
                cooldown_symbols=state.cooldown_symbols,
                consecutive_losses=state.consecutive_losses,
                max_consecutive_losses=state.max_consecutive_losses,
            )

        order = OrderRequest(
            symbol=intent.symbol,
            side=intent.side,
            quantity=abs(intent.quantity or 0.0),
            order_type=order_type,
            limit_price=limit_price,
            asset_class=asset_class,
            notional_usd=abs(intent.notional or 0.0),
        )
        decision = self.evaluate(order, account, market, risk_state)
        decision_reasons = list(decision.reasons)
        if not intent.adds_risk:
            exit_only_exemptions = {
                "order notional must be positive and known",
                "insufficient buying power",
                "max open positions reached",
            }
            decision_reasons = [reason for reason in decision_reasons if reason not in exit_only_exemptions]
        reasons.extend(decision_reasons)
        return intent.with_risk_decision(approved=not reasons, blocks=tuple(reasons))


def material_rejection(reasons: Iterable[str]) -> bool:
    material = {"kill switch is enabled", "max daily loss reached", "max total drawdown reached"}
    return any(reason in material for reason in reasons)
