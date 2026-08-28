"""Generator strony www (sekcja 8.6): index.html + archiwum.html.

Sortowanie domyślne: termin składania rosnąco (najpilniejsze u góry),
brak-terminu na końcu. Okno wyświetlania: termin w przyszłości LUB publikacja
w ostatnich N dniach; starsze -> archiwum.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def _sort_key(a: dict):
    return a.get("termin_skladania") or "9999-12-31"


def render_site(announcements_path: str, out_dir: str, display_days: int = 30) -> None:
    with open(announcements_path, encoding="utf-8") as f:
        items = json.load(f)

    items.sort(key=_sort_key)
    now = datetime.now()
    cutoff_pub = (now - timedelta(days=display_days)).date().isoformat()

    current, archive = [], []
    for a in items:
        term = (a.get("termin_skladania") or "")[:10]
        pub = (a.get("data_publikacji") or "")[:10]
        # ogłoszenia bez żadnej daty pokazujemy w „aktualnych" — nie znikają bezsłusznie
        if not term and not pub:
            current.append(a)
        elif (term and term >= now.date().isoformat()) or (pub and pub >= cutoff_pub):
            current.append(a)
        else:
            archive.append(a)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES), autoescape=True,
        trim_blocks=True, lstrip_blocks=True,
    )
    today = now.date().isoformat()
    d7 = (now + timedelta(days=7)).date().isoformat()
    d14 = (now + timedelta(days=14)).date().isoformat()
    ctx = {
        "current": current,
        "archive": archive,
        "generated": now.strftime("%Y-%m-%d %H:%M"),
        "generated_date": today,
        "deadline_7": d7,
        "deadline_14": d14,
        "display_days": display_days,
        "failed_sources": [],  # uzupełniane przez run.py w razie awarii
    }
    os.makedirs(out_dir, exist_ok=True)
    for tpl, name in (("index.html.j2", "index.html"), ("archiwum.html.j2", "archiwum.html")):
        html = env.get_template(tpl).render(**ctx)
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(html)
