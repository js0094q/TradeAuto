from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from trading_system.trading.order_intents import OrderIntent


@dataclass(frozen=True)
class RankingSnapshot:
    symbol: str
    rank: int
    return_60d: float
    above_sma_200: bool
    indicators: dict[str, float | int | str | bool | None] = field(default_factory=dict)
    risk_blocks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "rank": self.rank,
            "return_60d": self.return_60d,
            "above_sma_200": self.above_sma_200,
            **self.indicators,
            "risk_blocks": list(self.risk_blocks),
        }


@dataclass(frozen=True)
class StrategySelection:
    symbol: str
    target_weight: float
    reason: str
    indicators: dict[str, float | int | str | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "target_weight": self.target_weight,
            "reason": self.reason,
            "indicators": self.indicators,
        }


@dataclass(frozen=True)
class StrategyExit:
    symbol: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"symbol": self.symbol, "reason": self.reason}


@dataclass(frozen=True)
class StrategyRebalance:
    strategy_name: str
    mode: str
    timestamp: datetime
    regime: dict[str, float | int | str | bool | None]
    rankings: tuple[RankingSnapshot, ...] = ()
    selected: tuple[StrategySelection, ...] = ()
    exits: tuple[StrategyExit, ...] = ()
    risk_blocks: tuple[str, ...] = ()
    orders: tuple[OrderIntent, ...] = ()
    indicator_snapshot: dict[str, dict[str, float | int | str | bool | None]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dashboard_payload(self) -> dict[str, Any]:
        timestamp = self.timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return {
            "strategy_name": self.strategy_name,
            "mode": self.mode,
            "timestamp": timestamp,
            "regime": self.regime,
            "rankings": [item.to_dict() for item in self.rankings],
            "selected": [item.to_dict() for item in self.selected],
            "exits": [item.to_dict() for item in self.exits],
            "risk_blocks": list(self.risk_blocks),
            "orders": [
                {
                    "strategy_name": order.strategy_name,
                    "symbol": order.symbol,
                    "side": order.side,
                    "target_weight": order.target_weight,
                    "quantity": order.quantity,
                    "notional": order.notional,
                    "reason": order.reason,
                    "risk_approved": order.risk_approved,
                    "risk_blocks": list(order.risk_blocks),
                    "mode": order.mode,
                }
                for order in self.orders
            ],
            "indicator_snapshot": self.indicator_snapshot,
            "warnings": list(self.warnings),
        }

    def telegram_summary(self) -> str:
        selected = ", ".join(f"{item.symbol} {item.target_weight * 100:.1f}%" for item in self.selected) or "none"
        exits = ", ".join(f"{item.symbol} {item.reason}" for item in self.exits) or "none"
        risk_blocks = ", ".join(self.risk_blocks) or "none"
        regime_label = "RISK_ON" if self.regime.get("risk_on") else "RISK_OFF"
        next_action = "paper rebalance only" if self.mode != "live" else "live rebalance gated"
        return "\n".join(
            (
                f"Strategy: {self.strategy_name}",
                f"Mode: {self.mode}",
                f"Regime: {regime_label}",
                f"Selected: {selected}",
                f"Exits: {exits}",
                f"Risk blocks: {risk_blocks}",
                f"Next action: {next_action}",
            )
        )


def blocked_trade_alert(strategy_name: str, mode: str, symbol: str, reason: str) -> str:
    return "\n".join(
        (
            f"Strategy: {strategy_name}",
            f"Mode: {mode}",
            f"Signal blocked: {symbol}",
            f"Reason: {reason}",
            "Action: no order sent",
        )
    )
