from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

if __package__ in (None, ""):
    # Allow importing when executed from `src/` as a script path.
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.collector import MarketPoint


@dataclass
class NormalizedPoint:
    name: str
    value: float | None
    change_pct: float | None
    direction: str
    is_dummy: bool = False


def calc_direction(change_pct: float | None) -> str:
    if change_pct is None:
        return "flat"
    if change_pct > 0:
        return "up"
    if change_pct < 0:
        return "down"
    return "flat"


def validate_change_range(change_pct: float | None, threshold: float = 20.0) -> tuple[bool, str | None]:
    if change_pct is None:
        return False, "등락률이 비어 있습니다."
    if abs(change_pct) > threshold:
        return False, f"등락률이 비정상 범위를 초과했습니다. change_pct={change_pct:.2f}%"
    return True, None


def normalize_market_point(point: MarketPoint) -> tuple[NormalizedPoint, list[str]]:
    errors: list[str] = []

    ok, message = validate_change_range(point.change_pct)
    if not ok and message:
        errors.append(f"[{point.name}] {message}")

    normalized = NormalizedPoint(
        name=point.name,
        value=round(point.value, 2),
        change_pct=round(point.change_pct, 2),
        direction=calc_direction(point.change_pct),
        is_dummy=False,
    )
    return normalized, errors


def normalize_dummy(name: str, value: float, change_pct: float) -> NormalizedPoint:
    return NormalizedPoint(
        name=name,
        value=round(value, 2),
        change_pct=round(change_pct, 2),
        direction=calc_direction(change_pct),
        is_dummy=True,
    )
