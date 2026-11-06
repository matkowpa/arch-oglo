"""Wybór frazy dla runu pz-search (jedno żądanie na run, Crawl-delay 900).

Dlaczego nie „po godzinie startu": GitHub potrafi odpalić cron z kilkugodzinnym
opóźnieniem (obserwacja 2026-09…11: 4–16 h). Stary wybór `hour - 5` brał wtedy
frazę innego slotu — jedna fraza wypadała dwa razy, inna wcale, a pomiar per
fraza („pz-search:<slug>") pokazywał fałszywe zera. `github.event.schedule`
niesie cron, który faktycznie wywołał run, więc mapowanie cron → fraza jest
odporne na opóźnienie.

Ręczny dispatch z frazą ma priorytet (diagnostyka pojedynczej frazy), a dispatch
bez frazy wraca do rotacji dziennej — tak jak dotąd.
"""
from __future__ import annotations

import os
from datetime import date


def _norm(cron: str | None) -> str:
    return " ".join((cron or "").split())


def phrase_for_schedule(cfg: dict, schedule: str | None) -> str | None:
    """Fraza przypisana do cronu, który odpalił run (None, gdy brak dopasowania)."""
    target = _norm(schedule)
    if not target:
        return None
    for slot in cfg.get("slots") or []:
        if isinstance(slot, dict) and _norm(slot.get("cron")) == target:
            return slot.get("phrase") or None
    return None


def phrase_for_day(cfg: dict, day: date | None = None) -> str | None:
    """Rotacja dzienna — fallback dla dispatchu bez frazy."""
    phrases = cfg.get("phrases") or []
    if not phrases:
        return None
    return phrases[(day or date.today()).day % len(phrases)]


def choose(cfg: dict, schedule: str | None = None,
           override: str | None = None, day: date | None = None) -> str | None:
    if override:
        return override
    return phrase_for_schedule(cfg, schedule) or phrase_for_day(cfg, day)


def main() -> int:
    import yaml

    with open("config/sources.yaml", encoding="utf-8") as f:
        cfg = (yaml.safe_load(f) or {}).get("platformazakupowa_search") or {}
    phrase = choose(cfg, os.environ.get("SCHEDULE"), os.environ.get("OVERRIDE"))
    print(phrase or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
