from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


def build_environment(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_market_summary(template_dir: Path, context: dict[str, Any]) -> str:
    env = build_environment(template_dir)
    template = env.get_template("market_summary.html.j2")
    return template.render(**context)


def save_html(output_path: Path, html: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def save_json(output_path: Path, payload: dict[str, Any]) -> None:
    import json

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def timestamp_kst() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
