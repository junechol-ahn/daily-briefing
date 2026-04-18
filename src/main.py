from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

import yaml

if __package__ in (None, ""):
    # Allow running as `python src/main.py` by adding repository root to sys.path.
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.collector import DataCollectionError, collect_latest_market_point
from src.normalize import normalize_dummy, normalize_market_point
from src.render import render_market_summary, save_html, save_json, timestamp_kst

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "symbols.yml"
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
RAW_DIR = BASE_DIR / "data" / "raw"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def collect_section_points(items: list[dict]) -> tuple[list, list[str], str | None]:
    errors: list[str] = []
    points = []
    as_of_date = None

    for item in items:
        try:
            point = collect_latest_market_point(
                key=item["key"],
                name=item["name"],
                symbol=item["symbol"],
            )
            normalized, point_errors = normalize_market_point(point)
            points.append(normalized)
            errors.extend(point_errors)
            as_of_date = as_of_date or point.as_of_date
        except DataCollectionError as exc:
            errors.append(str(exc))
            points.append(
                normalize_dummy(item["name"], value=0.0, change_pct=0.0)
            )

    return points, errors, as_of_date


def apply_section_fallback(
    points: list,
    fallback: list[dict],
) -> list:
    if any(not p.is_dummy for p in points):
        return points
    return [normalize_dummy(x["name"], x["value"], x["change_pct"]) for x in fallback]


def build_report_payload(config: dict) -> tuple[dict, list[str]]:
    domestic_points, domestic_errors, domestic_date = collect_section_points(config["domestic"])
    global_points, global_errors, global_date = collect_section_points(config["global"])
    fx_points, fx_errors, fx_date = collect_section_points(config["fx"])
    commodity_points, commodity_errors, commodity_date = collect_section_points(config["commodities"])

    errors = domestic_errors + global_errors + fx_errors + commodity_errors

    fallback = config.get("fallback", {})
    global_points = apply_section_fallback(global_points, fallback.get("global", []))
    fx_points = apply_section_fallback(fx_points, fallback.get("fx", []))
    commodity_points = apply_section_fallback(commodity_points, fallback.get("commodities", []))

    as_of_date = domestic_date or global_date or fx_date or commodity_date
    if not as_of_date:
        as_of_date = datetime.now().strftime("%Y-%m-%d")

    payload = {
        "as_of_date": as_of_date,
        "generated_at": timestamp_kst(),
        "sections": {
            "domestic": [p.__dict__ for p in domestic_points],
            "global": [p.__dict__ for p in global_points],
            "fx": [p.__dict__ for p in fx_points],
            "commodities": [p.__dict__ for p in commodity_points],
        },
        "errors": errors,
    }
    return payload, errors


def main() -> None:
    config = load_config()
    payload, _ = build_report_payload(config)

    html = render_market_summary(
        TEMPLATE_DIR,
        {
            "title": "전일 시장 요약",
            "as_of_date": payload["as_of_date"],
            "generated_at": payload["generated_at"],
            "sections": payload["sections"],
            "errors": payload["errors"],
        },
    )

    day = payload["as_of_date"]
    save_html(OUTPUT_DIR / f"{day}_market_summary.html", html)
    save_json(RAW_DIR / f"{day}_market_summary.json", payload)


if __name__ == "__main__":
    main()
