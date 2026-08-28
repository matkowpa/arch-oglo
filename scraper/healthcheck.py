"""Healthcheck — dwie metryki osobno (sekcja 8.4) + heartbeat (8.5).

(a) dostępność — źródło odpowiedziało poprawnie?  -> ::error:: gdy nie
(b) wydajność — wyników/run vs 7-dniowa średnia krocząca -> ::warning:: przy spadku >80%

data/history/ commitowane przy KAŻDYM runie = heartbeat przeciw wyłączeniu
scheduled workflow po 60 dniach bez commitów.
"""
from __future__ import annotations

import json
import os
from datetime import date
from statistics import mean

WARN_DROP = 0.8


def record_run(history_dir: str, per_source: dict[str, dict]) -> str:
    """per_source: {zrodlo: {ok: bool, count: int}} -> ścieżka zapisanego pliku."""
    os.makedirs(history_dir, exist_ok=True)
    path = os.path.join(history_dir, f"{date.today().isoformat()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(per_source, f, ensure_ascii=False, indent=1)
    return path


def check(history_dir: str, today: dict[str, dict]) -> list[str]:  # -> list[GH Actions log lines]
    lines: list[str] = []
    # (a) dostępność
    for src, st in today.items():
        if not st.get("ok", False):
            lines.append(f"::error::source {src} unreachable/unparsed")
    # (b) wydajność — 7-dniowa średnia krocząca
    past = [f for f in os.listdir(history_dir) if f.endswith(".json")]
    past.sort()
    daily_counts: dict[str, list[int]] = {}
    for fn in past[:-1]:  # bez dzisiejszego
        try:
            with open(os.path.join(history_dir, fn), encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue
        for src, st in d.items():
            if st.get("ok"):
                daily_counts.setdefault(src, []).append(st.get("count", 0))
    for src, st in today.items():
        hist = daily_counts.get(src, [])[-7:]
        if hist and st.get("ok"):
            avg = mean(hist)
            if avg > 0 and st.get("count", 0) < WARN_DROP * avg:
                lines.append(
                    f"::warning::source {src} yield dropped: {st.get('count')} vs avg {avg:.1f}"
                )
    return lines
