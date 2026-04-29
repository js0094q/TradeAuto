from __future__ import annotations

import math
from dataclasses import asdict

from trading_system.research.backtesting.metrics import BacktestMetrics


def summarize_metrics(metrics: BacktestMetrics) -> dict[str, object]:
    profit_factor: float | str = metrics.profit_factor
    if math.isinf(metrics.profit_factor):
        profit_factor = "inf"
    return {
        "total_return": metrics.total_return,
        "sharpe": metrics.sharpe,
        "sortino": metrics.sortino,
        "max_drawdown": metrics.max_drawdown,
        "win_rate": metrics.win_rate,
        "profit_factor": profit_factor,
        "trade_count": metrics.trade_count,
        "slippage_adjusted_return": metrics.slippage_adjusted_return,
        "by_symbol": asdict(metrics)["by_symbol"],
        "by_regime": asdict(metrics)["by_regime"],
        "by_time_of_day": asdict(metrics)["by_time_of_day"],
    }
