from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import FinanceDataReader as fdr


@dataclass
class MarketPoint:
    key: str
    name: str
    symbol: str
    value: float
    prev_value: float
    change_pct: float
    as_of_date: str


class DataCollectionError(RuntimeError):
    """Raised when market data cannot be collected for a symbol."""


def _extract_close_column(frame: Any) -> list[float]:
    if frame is None or frame.empty:
        return []

    # FDR returns a DataFrame with a Close column for index/ticker series.
    close_series = frame.get("Close")
    if close_series is None:
        return []

    # Drop NaN and convert to plain list.
    cleaned = close_series.dropna().tolist()
    return [float(v) for v in cleaned]


def _symbol_candidates(symbol: str) -> list[str]:
    """Return symbol fallback candidates for providers with unstable aliases."""
    aliases = {
        "000001.SS": ["SSEC", "000001", "SSE"],
    }
    return [symbol, *aliases.get(symbol, [])]


def collect_latest_market_point(*, key: str, name: str, symbol: str, lookback_days: int = 20) -> MarketPoint:
    end = date.today()
    start = end - timedelta(days=lookback_days)

    last_error: Exception | None = None
    frame = None
    used_symbol = symbol

    for candidate in _symbol_candidates(symbol):
        try:
            frame = fdr.DataReader(candidate, start.isoformat(), end.isoformat())
        except Exception as exc:
            last_error = exc
            continue

        closes = _extract_close_column(frame)
        if len(closes) >= 2:
            used_symbol = candidate
            break

    closes = _extract_close_column(frame)
    if len(closes) < 2:
        tried = ", ".join(_symbol_candidates(symbol))
        if last_error is not None:
            raise DataCollectionError(
                f"유효 종가 데이터가 부족합니다. symbol={symbol}, tried=[{tried}], 원인={last_error}"
            )
        raise DataCollectionError(
            f"유효 종가 데이터가 부족합니다. symbol={symbol}, tried=[{tried}], closes={len(closes)}"
        )

    prev_close, latest_close = closes[-2], closes[-1]
    if prev_close == 0:
        raise DataCollectionError(f"이전 종가가 0입니다. symbol={used_symbol}")

    change_pct = ((latest_close - prev_close) / prev_close) * 100.0
    as_of = frame.dropna().index[-1]

    return MarketPoint(
        key=key,
        name=name,
        symbol=used_symbol,
        value=latest_close,
        prev_value=prev_close,
        change_pct=change_pct,
        as_of_date=as_of.strftime("%Y-%m-%d"),
    )
