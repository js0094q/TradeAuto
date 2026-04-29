# Strategy Pattern Mining

This second-pass research mines read-only Alpaca historical data, Yahoo chart history, and Nasdaq earnings-calendar events for trigger patterns, entry timing, and failure modes. No order endpoints were called and live trading was not enabled.

| Strategy | Observations | Avg Forward Return | Positive Rate | Avg Max Adverse |
| --- | --- | --- | --- | --- |
| cross_sectional_momentum_rotation_v1 | 758 | 0.79% | 61.7% | -4.39% |
| crypto_trend_breakout_v1 | 238 | 2.49% | 58.4% | -10.92% |
| etf_time_series_momentum_v1 | 864 | 0.50% | 59.6% | -4.27% |
| opening_range_breakout_v1 | 72 | 0.34% | 69.4% | -0.51% |
| post_earnings_drift_v1 | 1 | 6.00% | 100.0% | -0.23% |
| vwap_mean_reversion_v1 | 50 | 0.02% | 58.0% | -0.30% |

## Strategy Notes

### etf_time_series_momentum_v1
Observed 864 triggers. Entry timing should remain tied to `fresh_50_200_momentum_alignment` only after strategy-specific suppression checks pass.
| Symbol | Date | Trigger | Entry Timing | Forward Return | Notes |
| --- | --- | --- | --- | --- | --- |
| XLE | 2021-02-02 | fresh_50_200_momentum_alignment | next daily bar after close confirmation | 24.53% | ret20=5.48%; ret60=35.36% |
| XLE | 2022-01-03 | fresh_50_200_momentum_alignment | next daily bar after close confirmation | 19.33% | ret20=3.77%; ret60=4.26% |
| XLE | 2022-10-04 | fresh_50_200_momentum_alignment | next daily bar after close confirmation | 14.52% | ret20=0.18%; ret60=12.92% |
| XLE | 2026-01-08 | fresh_50_200_momentum_alignment | next daily bar after close confirmation | 14.39% | ret20=1.86%; ret60=7.78% |
| IWM | 2020-11-03 | fresh_50_200_momentum_alignment | next daily bar after close confirmation | 14.17% | ret20=2.30%; ret60=1.55% |

### cross_sectional_momentum_rotation_v1
Observed 758 triggers. Entry timing should remain tied to `top_cross_sectional_60d_momentum` only after strategy-specific suppression checks pass.
| Symbol | Date | Trigger | Entry Timing | Forward Return | Notes |
| --- | --- | --- | --- | --- | --- |
| XLE | 2021-02-01 | top_cross_sectional_60d_momentum | weekly rank review, next daily bar | 24.09% | rank_score=34.06% |
| XLE | 2022-09-30 | top_cross_sectional_60d_momentum | weekly rank review, next daily bar | 23.94% | rank_score=1.47% |
| XLE | 2022-05-09 | top_cross_sectional_60d_momentum | weekly rank review, next daily bar | 21.06% | rank_score=11.17% |
| XLC | 2022-12-28 | top_cross_sectional_60d_momentum | weekly rank review, next daily bar | 18.44% | rank_score=-5.18% |
| XLE | 2021-02-08 | top_cross_sectional_60d_momentum | weekly rank review, next daily bar | 17.55% | rank_score=29.88% |

### opening_range_breakout_v1
Observed 72 triggers. Entry timing should remain tied to `15m_opening_range_high_break` only after strategy-specific suppression checks pass.
| Symbol | Date | Trigger | Entry Timing | Forward Return | Notes |
| --- | --- | --- | --- | --- | --- |
| NVDA | 2026-04-24 | 15m_opening_range_high_break | first close above opening-range high after blackout window | 2.40% | volume_confirmed; entry_time=10:34 ET |
| AAPL | 2026-04-15 | 15m_opening_range_high_break | first close above opening-range high after blackout window | 2.18% | volume_confirmed; entry_time=10:15 ET |
| IWM | 2026-04-02 | 15m_opening_range_high_break | first close above opening-range high after blackout window | 2.10% | volume_unconfirmed; entry_time=09:46 ET |
| NVDA | 2026-04-27 | 15m_opening_range_high_break | first close above opening-range high after blackout window | 2.01% | volume_confirmed; entry_time=12:33 ET |
| NVDA | 2026-04-02 | 15m_opening_range_high_break | first close above opening-range high after blackout window | 1.97% | volume_unconfirmed; entry_time=09:58 ET |

### vwap_mean_reversion_v1
Observed 50 triggers. Entry timing should remain tied to `below_vwap_stretch` only after strategy-specific suppression checks pass.
| Symbol | Date | Trigger | Entry Timing | Forward Return | Notes |
| --- | --- | --- | --- | --- | --- |
| IWM | 2026-04-07 | below_vwap_stretch | after 30 minutes, exit check at 30 minutes | 0.62% | vwap_deviation=-0.41% |
| NVDA | 2026-04-14 | below_vwap_stretch | after 30 minutes, exit check at 30 minutes | 0.60% | vwap_deviation=-0.36% |
| AAPL | 2026-04-09 | below_vwap_stretch | after 30 minutes, exit check at 30 minutes | 0.50% | vwap_deviation=-0.58% |
| IWM | 2026-04-06 | below_vwap_stretch | after 30 minutes, exit check at 30 minutes | 0.42% | vwap_deviation=-0.46% |
| NVDA | 2026-04-06 | below_vwap_stretch | after 30 minutes, exit check at 30 minutes | 0.41% | vwap_deviation=-0.43% |

### post_earnings_drift_v1
Observed 1 triggers. Entry timing should remain tied to `nasdaq_earnings_gap_up` only after strategy-specific suppression checks pass.
| Symbol | Date | Trigger | Entry Timing | Forward Return | Notes |
| --- | --- | --- | --- | --- | --- |
| UNH | 2026-04-21 | nasdaq_earnings_gap_up | unknown timing: require first-session confirmation | 6.00% | gap=9.13%; eps_forecast=$6.46; fiscal_quarter=Mar/2026 |

### crypto_trend_breakout_v1
Observed 238 triggers. Entry timing should remain tied to `20d_high_breakout` only after strategy-specific suppression checks pass.
| Symbol | Date | Trigger | Entry Timing | Forward Return | Notes |
| --- | --- | --- | --- | --- | --- |
| ETH/USD | 2021-04-28 | 20d_high_breakout | daily close confirmation; 24/7 monitoring required | 42.34% | weekday |
| ETH/USD | 2021-05-01 | 20d_high_breakout | daily close confirmation; 24/7 monitoring required | 41.76% | weekend |
| ETH/USD | 2021-04-27 | 20d_high_breakout | daily close confirmation; 24/7 monitoring required | 30.55% | weekday |
| BTC/USD | 2023-01-10 | 20d_high_breakout | daily close confirmation; 24/7 monitoring required | 30.00% | weekday |
| ETH/USD | 2025-07-09 | 20d_high_breakout | daily close confirmation; 24/7 monitoring required | 29.78% | weekday |

## Research Interpretation

- ETF and cross-sectional momentum should focus on fresh alignment/rank-change events instead of continuously firing on every qualifying day.
- Opening-range breakout should treat the first confirmed close outside the opening range as the candidate event and continue suppressing the first minute after open.
- VWAP mean reversion needs trend-day suppression; below-VWAP stretches can continue lower before reverting.
- Post-earnings drift remains event-data-limited: Nasdaq calendar supplies event timing, but surprise/revision data is still needed before promotion.
- Crypto breakout remains separate because weekend/weekday and 24/7 monitoring behavior materially changes trigger risk.

## Source Notes

- Alpaca historical market data: https://docs.alpaca.markets/docs/market-data
- Yahoo chart history endpoint: https://query1.finance.yahoo.com/v8/finance/chart/{symbol}
- Nasdaq earnings calendar: https://www.nasdaq.com/market-activity/earnings
