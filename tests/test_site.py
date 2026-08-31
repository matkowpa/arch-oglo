"""Testy generatora strony: licznik/filtr „dodane w dniu X” (pole dodano)."""
import json
import os
from datetime import date, timedelta

from scraper.site import render_site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _item(url, dodano=None):
    return {
        "zrodlo": "ted",
        "tytul": "Tytuł " + url,
        "url": url,
        "zamawiajacy": "Zamawiający",
        "data_publikacji": None,
        "termin_skladania": "2030-01-01T09:00:00+02:00",  # przyszły termin -> „aktualne”
        "opis": None,
        "cpv": [],
        "score": 5,
        "tagi": [],
        "status_opisu": "brak",
        "dodano": dodano,
    }


def _render(tmp_path, items):
    src = tmp_path / "announcements.json"
    src.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "site"
    render_site(str(src), str(out))
    with open(os.path.join(out, "index.html"), encoding="utf-8") as f:
        return f.read()


def test_added_filter_options_with_counts(tmp_path):
    today = date.today().isoformat()
    yday = (date.today() - timedelta(days=1)).isoformat()
    items = [
        _item("https://x/1", today),
        _item("https://x/2", today),   # dwa runy w tym samym dniu agregują się
        _item("https://x/3", yday),
        _item("https://x/4", None),    # wpis sprzed zmiany — nie liczony
    ]
    html = _render(tmp_path, items)
    assert f'value="{today}">Dodane: Dzisiaj (2)' in html
    assert f'value="{yday}">Dodane: Wczoraj (1)' in html


def test_added_data_attribute_on_cards(tmp_path):
    today = date.today().isoformat()
    html = _render(tmp_path, [_item("https://x/1", today), _item("https://x/2", None)])
    assert f'data-added="{today}"' in html
    assert 'data-added=""' in html  # wpis bez dodano nie pasuje do żadnego dnia
