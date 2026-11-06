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


def _past_item(url, termin):
    item = _item(url)
    item["termin_skladania"] = termin
    return item


def test_nearest_lists_only_future_deadlines(tmp_path):
    items = [
        _past_item("https://x/old", "2020-01-01T09:00:00+01:00"),
        _past_item("https://x/soon", "2030-01-01T09:00:00+01:00"),
    ]
    html = _render(tmp_path, items)
    nearest = html.split('Pilne terminy')[1].split('</aside>')[0]
    assert "2030-01-01" in nearest
    assert "2020-01-01" not in nearest


def test_a_stored_description_is_shown_on_the_card(tmp_path):
    item = _item("https://x/1")
    item["opis"] = "Przedmiotem zamówienia jest opracowanie dokumentacji projektowej."
    html = _render(tmp_path, [item])
    assert "Przedmiotem zamówienia jest opracowanie dokumentacji" in html


def test_a_ted_summary_is_shown_when_there_is_no_description(tmp_path):
    item = _item("https://x/1")
    item["streszczenie"] = "Przedmiotem zamówienia jest nadzór inwestorski."
    html = _render(tmp_path, [item])
    assert "nadzór inwestorski" in html
