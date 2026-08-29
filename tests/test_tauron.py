"""Testy parsera SWOZ Grupy TAURON (swoz.tauron.pl) — wyłącznie na fixture."""
import os

from scraper.sources.bip.tauron import TauronSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CFG = {"list_url": "https://swoz.tauron.pl/platform/demand/notice/public/current/list"}


def _parse_fixture():
    fixture = os.path.join(ROOT, "tests", "fixtures", "tauron_swoz_list.html")
    with open(fixture, encoding="utf-8") as f:
        html = f.read()
    return TauronSource(CFG).parse(html, base_url=CFG["list_url"])


def test_tauron_parser_finds_rows():
    items = _parse_fixture()
    assert items, "parser nie znalazł ogłoszeń na fixture SWOZ"
    assert len(items) >= 20  # ~25-30 wierszy/stronę


def test_tauron_fields():
    items = _parse_fixture()
    first = items[0]
    assert first.zrodlo == "bip:tauron"
    assert first.tytul
    assert first.zamawiajacy.startswith("TAURON")  # np. TAURON Ciepło sp. z o.o.
    assert first.data_publikacji and len(first.data_publikacji) == 10
    assert first.termin_skladania  # ISO date lub ISO datetime
    assert first.status_opisu == "brak"
    # url fallback = strona listy (wiersz nie zawiera linku do szczegółów)
    assert first.url == CFG["list_url"]


def test_tauron_distinct_hashes():
    items = _parse_fixture()
    hashes = {i.hash for i in items}
    assert len(hashes) == len(items)  # różne tytuły -> różne hashe mimo wspólnego URL


def test_tauron_empty_table():
    assert TauronSource(CFG).parse("<html><body>brak tabeli</body></html>") == []


def test_tauron_in_build_sources():
    from scraper.run import build_sources

    names = [s.name for s in build_sources()]
    assert "bip:tauron" in names
    assert "bip:phn" in names
