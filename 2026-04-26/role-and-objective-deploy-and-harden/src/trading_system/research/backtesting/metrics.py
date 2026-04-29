from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from trading_system.research.backtesting.costs import CostAssumptions, estimate_round_trip_cost


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    side: str = "long"
    holding_period_minutes: float = 0.0
    regime: str = "unknown"
    entry_time_of_day: str = "unknown"
    sector: str = "unknown"

    @property
    def gross_pnl(self) -> float:
        direction = 1.0 if self.side == "long" else -1.0
        return (self.exit_price - self.entry_price) * self.quantity * direction

    @property
    def entry_notional(self) -> float:
        return abs(self.entry_price * self.quantity)

    @property
    def exit_notional(self) -> float:
        return abs(self.exit_price * self.quantity)


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    annualized_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    expectancy_per_trade: float
    exposure_time: float
    turnover: float
    average_holding_period: float
    trade_count: int
    worst_trade: float
    best_trade: float
    longest_losing_streak: int
    slippage_adjusted_return: float
    spread_adjusted_return: float
    by_symbol: dict[str, float]
    by_regime: dict[str, float]
    by_time_of_day: dict[str, float]


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _profit_factor(total_gain: float, total_loss: float) -> float:
    if total_loss == 0:
        return float("inf") if total_gain > 0 else 0.0
    return total_gain / total_loss


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        worst = min(worst, value - peak)
    return abs(worst)


def _longest_losing_streak(pnls: list[float]) -> int:
    longest = 0
    current = 0
    for pnl in pnls:
        if pnl < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _group_pnl(trades: list[Trade], net_pnls: list[float], attr: str) -> dict[str, float]:
    grouped: dict[str, float] = {}
    for trade, pnl in zip(trades, net_pnls, strict=True):
        key = str(getattr(trade, attr))
        grouped[key] = grouped.get(key, 0.0) + pnl
    return grouped


def calculate_metrics(
    trades: list[Trade],
    *,
    starting_equity: float = 100_000.0,
    assumptions: CostAssumptions,
    periods_per_year: float = 252.0,
) -> BacktestMetrics:
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")
    gross_pnls = [trade.gross_pnl for trade in trades]
    costs = [
        estimate_round_trip_cost(
            trade.entry_notional,
            trade.quantity,
            sell_notional=trade.exit_notional,
            assumptions=assumptions,
        )
        for trade in trades
    ]
    net_pnls = [gross - cost for gross, cost in zip(gross_pnls, costs, strict=True)]
    equity = starting_equity
    equity_curve = [equity]
    for pnl in net_pnls:
        equity += pnl
        equity_curve.append(equity)
    total_pnl = sum(net_pnls)
    total_return = total_pnl / starting_equity
    trade_returns = [pnl / starting_equity for pnl in net_pnls]
    mean_return = statistics.fmean(trade_returns) if trade_returns else 0.0
    return_std = statistics.pstdev(trade_returns) if len(trade_returns) > 1 else 0.0
    downside = [value for value in trade_returns if value < 0]
    downside_std = statistics.pstdev(downside) if len(downside) > 1 else 0.0
    wins = [pnl for pnl in net_pnls if pnl > 0]
    losses = [pnl for pnl in net_pnls if pnl < 0]
    total_gain = sum(wins)
    total_loss = abs(sum(losses))
    trade_count = len(trades)
    years = max(1.0 / periods_per_year, trade_count / periods_per_year)
    adjusted_cost_return = sum(costs) / starting_equity
    return BacktestMetrics(
        total_return=total_return,
        annualized_return=((1.0 + total_return) ** (1.0 / years) - 1.0) if total_return > -1 else -1.0,
        sharpe=0.0 if return_std == 0 else mean_return / return_std * math.sqrt(periods_per_year),
        sortino=0.0 if downside_std == 0 else mean_return / downside_std * math.sqrt(periods_per_year),
        max_drawdown=_max_drawdown(equity_curve) / starting_equity,
        win_rate=_ratio(len(wins), trade_count),
        average_win=statistics.fmean(wins) if wins else 0.0,
        average_loss=statistics.fmean(losses) if losses else 0.0,
        profit_factor=_profit_factor(total_gain, total_loss),
        expectancy_per_trade=statistics.fmean(net_pnls) if net_pnls else 0.0,
        exposure_time=sum(trade.holding_period_minutes for trade in trades),
        turnover=sum(trade.entry_notional + trade.exit_notional for trade in trades) / starting_equity,
        average_holding_period=statistics.fmean([trade.holding_period_minutes for trade in trades]) if trades else 0.0,
        trade_count=trade_count,
        worst_trade=min(net_pnls) if net_pnls else 0.0,
        best_trade=max(net_pnls) if net_pnls else 0.0,
        longest_losing_streak=_longest_losing_streak(net_pnls),
        slippage_adjusted_return=total_return,
        spread_adjusted_return=total_return + adjusted_cost_return,
        by_symbol=_group_pnl(trades, net_pnls, "symbol"),
        by_regime=_group_pnl(trades, net_pnls, "regime"),
        by_time_of_day=_group_pnl(trades, net_pnls, "entry_time_of_day"),
    )
