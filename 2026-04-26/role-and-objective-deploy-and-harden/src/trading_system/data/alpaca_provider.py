from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from trading_system.broker.alpaca_cli import CliResult, AlpacaCli
from trading_system.data.models import MarketBar, OptionChain, OptionContract, Quote, Snapshot, Trade
from trading_system.data.provider import MarketDataProvider, MarketDataProviderError


def _to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _choose_first(data: Mapping[str, object], key: str, default: object = None) -> object:
    if key in data:
        return data[key]
    for candidate in (
        key.lower(),
        key.upper(),
        "data",
        "bars",
        f"bars_{key}",
    ):
        if candidate in data:
            return data[candidate]
    return default


@dataclass(frozen=True)
class CliRunner:
    profile: str
    timeout_seconds: int = 30

    def run(self, args: list[str]) -> CliResult:
        command = ["alpaca"]
        env = os.environ.copy()
        if self.profile:
            env["ALPACA_PROFILE"] = self.profile
            command.extend(["--profile", self.profile])
        command.extend(args)
        command.append("--quiet")
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=self.timeout_seconds,
            )
        except OSError as exc:
            return CliResult(
                ok=False,
                returncode=127,
                stdout="",
                stderr=f"alpaca cli unavailable: {exc}",
            )
        return CliResult(
            ok=completed.returncode == 0,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class AlpacaDataProvider(MarketDataProvider):
    """Read-only Alpaca provider for research and signal studies."""

    def __init__(
        self,
        *,
        runner: CliRunner | None = None,
        feed: str | None = None,
        option_feed: str | None = None,
        adjustment: str | None = "split",
    ) -> None:
        self._runner = runner or CliRunner(profile="paper")
        self.feed = feed or "sip"
        self.option_feed = option_feed or "opra"
        self.adjustment = adjustment

    def _run(self, *args: str, feed: str | None = None) -> Mapping[str, Any]:
        params = [
            "data",
            *args,
        ]
        if feed:
            params.extend(["--feed", str(feed)])
        result = self._runner.run(params)
        if not result.ok:
            raise MarketDataProviderError(result.stderr.strip() or result.stdout.strip() or "alpaca cli request failed")
        payload = json.loads(result.stdout or "{}")
        if isinstance(payload, dict):
            return payload
        raise MarketDataProviderError("unexpected alpaca response payload")

    def _as_symbol_bars(self, raw: Mapping[str, Any], *, symbols: tuple[str, ...]) -> dict[str, list[MarketBar]]:
        source = _choose_first(raw, "bars", {})
        if not isinstance(source, Mapping):
            return {}
        data: dict[str, list[MarketBar]] = {}
        for symbol in symbols:
            symbol_rows = source.get(symbol, [])
            if not isinstance(symbol_rows, list):
                continue
            bars: list[MarketBar] = []
            for row in symbol_rows:
                if not isinstance(row, Mapping):
                    continue
                timestamp = str(row.get("t") or row.get("time") or row.get("timestamp") or "")
                bars.append(
                    MarketBar(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=_to_float(row.get("o")),
                        high=_to_float(row.get("h")),
                        low=_to_float(row.get("l")),
                        close=_to_float(row.get("c")),
                        volume=_to_float(row.get("v")),
                        vwap=_to_float(row.get("vw")),
                    )
                )
            data[symbol] = bars
        return data

    def _fetch_paged_bars(
        self,
        base_args: tuple[str, ...],
        *,
        symbols: tuple[str, ...],
        feed: str | None,
    ) -> dict[str, list[MarketBar]]:
        collected: dict[str, list[MarketBar]] = {symbol: [] for symbol in symbols}
        page_token = ""
        while True:
            args = [*base_args, "--limit", "1000"]
            if page_token:
                args.extend(["--page-token", page_token])
            payload = self._run(*args, feed=feed)
            page = self._as_symbol_bars(payload, symbols=symbols)
            for symbol, bars in page.items():
                collected.setdefault(symbol, []).extend(bars)
            next_page = payload.get("next_page_token")
            page_token = str(next_page or "")
            if not page_token:
                break
        return {symbol: bars for symbol, bars in collected.items() if bars}

    def fetch_bars(
        self,
        symbols: tuple[str, ...],
        timeframe: str,
        start: str,
        end: str | None = None,
    ) -> dict[str, list[MarketBar]]:
        if not symbols:
            return {}
        return self._fetch_paged_bars(
            (
                "multi-bars",
                "--symbols", _maybe_joined_symbols(symbols),
                "--timeframe", timeframe,
                "--start", start,
                *(("--end", end) if end else ()),
                *(("--adjustment", self.adjustment) if self.adjustment else ()),
            ),
            symbols=tuple(sorted(symbols)),
            feed=self.feed,
        )

    def fetch_crypto_bars(
        self,
        symbols: tuple[str, ...],
        timeframe: str,
        start: str,
        end: str | None = None,
    ) -> dict[str, list[MarketBar]]:
        if not symbols:
            return {}
        return self._fetch_paged_bars(
            (
                "crypto",
                "bars",
                "--symbols", _maybe_joined_symbols(symbols),
                "--timeframe", timeframe,
                "--start", start,
                *(("--end", end) if end else ()),
            ),
            symbols=tuple(sorted(symbols)),
            feed=None,
        )

    def fetch_latest_quote(self, symbols: tuple[str, ...]) -> dict[str, Quote]:
        if not symbols:
            return {}
        payload = self._run("latest-quotes", "--symbols", _maybe_joined_symbols(symbols), feed=self.feed)
        results = _choose_first(payload, "quotes", {})
        if not isinstance(results, Mapping):
            return {}
        output: dict[str, Quote] = {}
        for symbol in symbols:
            details = results.get(symbol, {})
            if not isinstance(details, Mapping):
                continue
            output[symbol] = Quote(
                symbol=symbol,
                timestamp=str(_choose_first(details, "t", "") or ""),
                bid=_to_float(_choose_first(details, "bp", 0)),
                ask=_to_float(_choose_first(details, "ap", 0)),
                bid_size=_to_int(_choose_first(details, "bs", 0)),
                ask_size=_to_int(_choose_first(details, "as", 0)),
            )
        return output

    def fetch_latest_trade(self, symbols: tuple[str, ...]) -> dict[str, Trade]:
        if not symbols:
            return {}
        payload = self._run("latest-trades", "--symbols", _maybe_joined_symbols(symbols), feed=self.feed)
        results = _choose_first(payload, "trades", {})
        if not isinstance(results, Mapping):
            return {}
        output: dict[str, Trade] = {}
        for symbol in symbols:
            details = results.get(symbol, {})
            if not isinstance(details, Mapping):
                continue
            output[symbol] = Trade(
                symbol=symbol,
                timestamp=str(_choose_first(details, "t", "") or ""),
                price=_to_float(_choose_first(details, "p", 0)),
                size=_to_int(_choose_first(details, "s", 0)),
                exchange=str(_choose_first(details, "x", "")),
            )
        return output

    def fetch_snapshot(self, symbols: tuple[str, ...]) -> dict[str, Snapshot]:
        if not symbols:
            return {}
        payload = self._run("multi-snapshots", "--symbols", _maybe_joined_symbols(symbols), feed=self.feed)
        results = _choose_first(payload, "snapshots", payload)
        if not isinstance(results, Mapping):
            return {}
        output: dict[str, Snapshot] = {}
        for symbol in symbols:
            details = results.get(symbol, {})
            if not isinstance(details, Mapping):
                continue
            quote = details.get("latestQuote") if isinstance(details.get("latestQuote"), Mapping) else {}
            if not isinstance(quote, Mapping):
                quote = {}
            trade = details.get("latestTrade") if isinstance(details.get("latestTrade"), Mapping) else {}
            if not isinstance(trade, Mapping):
                trade = {}
            output[symbol] = Snapshot(
                symbol=symbol,
                timestamp=str(_choose_first(trade, "t", _choose_first(quote, "t", "")) or ""),
                price=_to_float(_choose_first(trade, "p", 0)),
                bid=_to_float(_choose_first(quote, "bp", 0)),
                ask=_to_float(_choose_first(quote, "ap", 0)),
                volume=_to_float(_choose_first(details, "dailyBar", {}).get("v", 0) if isinstance(_choose_first(details, "dailyBar", {}), Mapping) else 0),
            )
        return output

    def fetch_option_chain(self, underlying: str, expiration: str | None = None) -> OptionChain:
        args = ["option", "chain", "--underlying-symbol", underlying, "--limit", "100"]
        if expiration:
            args.extend(["--expiration-date", expiration])
        payload = self._run(*args, feed=self.option_feed)
        chain = _choose_first(payload, "snapshots", _choose_first(payload, "chain", {}))
        if not isinstance(chain, Mapping):
            chain = {}
        options: list[OptionContract] = []
        for symbol, item in chain.items():
            if not isinstance(item, Mapping):
                continue
            quote = item.get("latestQuote") if isinstance(item.get("latestQuote"), Mapping) else {}
            daily = item.get("dailyBar") if isinstance(item.get("dailyBar"), Mapping) else {}
            parsed = _parse_option_symbol(str(symbol))
            options.append(
                OptionContract(
                    symbol=str(symbol),
                    strike=parsed[1],
                    expiration=parsed[0],
                    right=parsed[2],
                    bid=_to_float(_choose_first(quote, "bp", 0)),
                    ask=_to_float(_choose_first(quote, "ap", 0)),
                    volume=_to_int(_choose_first(daily, "v", 0)),
                    open_interest=None,
                    implied_volatility=None,
                )
            )
        return OptionChain(
            underlying=underlying,
            expiration=expiration,
            contracts=tuple(options),
        )

    def fetch_option_quotes(self, contracts: tuple[str, ...]) -> dict[str, Quote]:
        if not contracts:
            return {}
        payload = self._run("option", "latest-quotes", "--symbols", _maybe_joined_symbols(contracts), feed=self.option_feed)
        results = _choose_first(payload, "quotes", {})
        if not isinstance(results, Mapping):
            return {}
        output: dict[str, Quote] = {}
        for symbol in contracts:
            details = results.get(symbol, {})
            if not isinstance(details, Mapping):
                continue
            output[symbol] = Quote(
                symbol=symbol,
                timestamp=str(_choose_first(details, "t", "") or ""),
                bid=_to_float(_choose_first(details, "bp", 0)),
                ask=_to_float(_choose_first(details, "ap", 0)),
                bid_size=_to_int(_choose_first(details, "bs", 0)),
                ask_size=_to_int(_choose_first(details, "as", 0)),
            )
        return output

    def fetch_option_snapshot(self, contracts: tuple[str, ...]) -> dict[str, Snapshot]:
        if not contracts:
            return {}
        payload = self._run("option", "snapshot", "--symbols", _maybe_joined_symbols(contracts), feed=self.option_feed)
        results = _choose_first(payload, "snapshots", {})
        if not isinstance(results, Mapping):
            return {}
        output: dict[str, Snapshot] = {}
        for symbol in contracts:
            details = results.get(symbol, {})
            if not isinstance(details, Mapping):
                continue
            quote = details.get("latestQuote") if isinstance(details.get("latestQuote"), Mapping) else {}
            if not isinstance(quote, Mapping):
                quote = {}
            trade = details.get("latestTrade") if isinstance(details.get("latestTrade"), Mapping) else {}
            if not isinstance(trade, Mapping):
                trade = {}
            daily = details.get("dailyBar") if isinstance(details.get("dailyBar"), Mapping) else {}
            if not isinstance(daily, Mapping):
                daily = {}
            output[symbol] = Snapshot(
                symbol=symbol,
                timestamp=str(_choose_first(trade, "t", _choose_first(quote, "t", "")) or ""),
                price=_to_float(_choose_first(trade, "p", 0)),
                bid=_to_float(_choose_first(quote, "bp", 0)),
                ask=_to_float(_choose_first(quote, "ap", 0)),
                volume=_to_float(_choose_first(daily, "v", 0)),
            )
        return output


def _maybe_joined_symbols(symbols: tuple[str, ...]) -> str:
    return ",".join(symbols)


def _parse_option_symbol(symbol: str) -> tuple[str, float, str]:
    if len(symbol) < 15:
        return "", 0.0, ""
    expiry = symbol[-15:-9]
    right = symbol[-9:-8]
    strike = symbol[-8:]
    if len(expiry) != 6 or right not in {"C", "P"} or not strike.isdigit():
        return "", 0.0, ""
    year = int(expiry[:2]) + 2000
    expiration = f"{year:04d}-{int(expiry[2:4]):02d}-{int(expiry[4:6]):02d}"
    return expiration, int(strike) / 1000.0, {"C": "call", "P": "put"}[right]
