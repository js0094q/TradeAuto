from __future__ import annotations

from trading_system.strategies.rebalance import StrategyRebalance, blocked_trade_alert


def format_rebalance_alert(rebalance: StrategyRebalance) -> str:
    return rebalance.telegram_summary()


def format_blocked_trade_alert(strategy_name: str, mode: str, symbol: str, reason: str) -> str:
    return blocked_trade_alert(strategy_name, mode, symbol, reason)
