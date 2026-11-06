"""Healthcheck — dwie metryki osobno (sekcja 8.4) + heartbeat (8.5).

(a) dostępność — źródło odpowiedziało poprawnie?  -> ::error:: gdy nie
(b) wydajność — wyników/run vs średnia z poprzednich dni -> ::warning:: przy spadku >80%
(c) lejek — źródło pobiera pozycje, ale od tygodnia nic nie publikuje -> ::warning::

data/history/ commitowane przy KAŻDYM runie = heartbeat przeciw wyłączeniu
scheduled workflow po 60 dniach bez commitów.

Plik dnia jest WSPÓLNY dla wszystkich runów (daily + osobne runy pz-search), a
workflow commituje go z `-X theirs`, więc każdy kolejny run nadpisywał poprzedni.
Dlatego `record_run` scala wpisy w obrębie dnia (sumuje count/kept, liczy runy), a
`check` porównuje wynik NA RUN, nie sumę dnia — inaczej dzień z jednym runem
wyglądałby jak załamanie wobec dnia z siedmioma.
"""
from __future__ import annotations

import json
import os
from datetime import date
from statistics import mean

WARN_DROP = 0.8          # spadek wyniku/run poniżej 80% średniej -> warning
ZERO_YIELD_DAYS = 5      # tyle dni z rzędu „coś pobrane, nic nie opublikowane” -> warning
AVERAGE_DAYS = 7


def _today() -> str:
    return date.today().isoformat()


def _merge_entry(old: dict | None, new: dict | None) -> dict:
    """Scal wpis źródła z dwóch runów tego samego dnia."""
    if not new:
        return dict(old or {})
    if not old:
        return {
            "ok": bool(new.get("ok")),
            "count": int(new.get("count") or 0),
            "kept": int(new.get("kept") or 0),
            "runs": 1,
        }
    return {
        "ok": bool(old.get("ok", True)) and bool(new.get("ok", True)),
        "count": int(old.get("count") or 0) + int(new.get("count") or 0),
        "kept": int(old.get("kept") or 0) + int(new.get("kept") or 0),
        "runs": int(old.get("runs") or 1) + 1,
    }


def record_run(history_dir: str, per_source: dict[str, dict]) -> str:
    """per_source: {zrodlo: {ok, count, kept}} -> ścieżka pliku dnia.

    Kilka runów dziennie (daily + osobne runy pz-search) dopisuje się do jednego
    pliku: count/kept się sumują, `runs` rośnie. Wcześniej każdy run nadpisywał
    plik, więc historia pokazywała tylko ostatnią frazę pz-search (zwykle 0).
    """
    os.makedirs(history_dir, exist_ok=True)
    path = os.path.join(history_dir, f"{_today()}.json")
    existing: dict = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f) or {}
        except (OSError, ValueError):
            existing = {}
    merged: dict = {}
    for name in list(existing) + [n for n in per_source if n not in existing]:
        old = existing.get(name)
        new = per_source.get(name)
        if not isinstance(old, dict) and not isinstance(new, dict):
            continue
        entry = _merge_entry(old if isinstance(old, dict) else None,
                             new if isinstance(new, dict) else None)
        if entry:
            merged[name] = entry
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    return path


def _history(history_dir: str, skip_today: bool = True) -> list[dict]:
    """Wpisy historii, najstarsze pierwsze; domyślnie bez dzisiejszego pliku."""
    if not os.path.isdir(history_dir):
        return []
    out = []
    for fn in sorted(f for f in os.listdir(history_dir) if f.endswith(".json")):
        if skip_today and fn[:-5] == _today():
            continue
        try:
            with open(os.path.join(history_dir, fn), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def _runs(entry: dict) -> int:
    """Liczba runów w wpisie; starsze pliki nie mają pola `runs` (= 1 run)."""
    try:
        return max(1, int(entry.get("runs") or 1))
    except (TypeError, ValueError):
        return 1


def check(history_dir: str, today: dict[str, dict]) -> list[str]:  # -> list[GH Actions log lines]
    lines: list[str] = []
    # (a) dostępność
    for src, st in today.items():
        if not st.get("ok", False):
            lines.append(f"::error::source {src} unreachable/unparsed")

    past = _history(history_dir)
    # (b) wydajność — średnia NA RUN z poprzednich dni (nie suma dnia)
    per_run: dict[str, list[float]] = {}
    fetched: dict[str, int] = {}
    kept: dict[str, int] = {}
    days: dict[str, int] = {}
    for entry in past[-AVERAGE_DAYS:]:
        for src, st in entry.items():
            if not isinstance(st, dict):
                continue
            if st.get("ok"):
                per_run.setdefault(src, []).append(int(st.get("count") or 0) / _runs(st))
            if "kept" in st:  # starsze pliki nie mają lejka
                fetched[src] = fetched.get(src, 0) + int(st.get("count") or 0)
                kept[src] = kept.get(src, 0) + int(st.get("kept") or 0)
                days[src] = days.get(src, 0) + 1
    for src, st in today.items():
        hist = per_run.get(src) or []
        if hist and st.get("ok"):
            avg = mean(hist)
            got = int(st.get("count") or 0) / _runs(st)
            if avg > 0 and got < WARN_DROP * avg:
                lines.append(
                    f"::warning::source {src} yield dropped: {got:.0f}/run vs avg {avg:.1f}/run"
                )

    # (c) lejek — pobiera, ale nie publikuje (cichy zgon filtra/mapowania)
    for src, st in today.items():
        if not st.get("ok") or "kept" not in st:
            continue
        total_fetched = fetched.get(src, 0) + int(st.get("count") or 0)
        total_kept = kept.get(src, 0) + int(st.get("kept") or 0)
        if days.get(src, 0) + 1 >= ZERO_YIELD_DAYS and total_fetched and not total_kept:
            lines.append(
                f"::warning::source {src} published 0 of {total_fetched} fetched over "
                f"{days[src] + 1} days (filter or mapping?)"
            )
    return lines
