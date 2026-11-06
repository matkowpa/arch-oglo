"""Testy źródła PGG (przetargi zakupowe) — wyłącznie na fixture.

Lista jest serwerowym HTML-em dopiero po POST `{ścieżka}-list` z tokenem CSRF;
`<main>` strony z listą jest pusty, bo resztę renderuje JS.
"""
import os

from scraper.sources.pgg import PggSource, _iso_date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = {
    "list_url": "https://www.pgg.pl/przetargi/przetargi-zakupowe/przed-terminem-skladania-ofert",
    "crawl_delay": 0,
}


def _fixture() -> str:
    with open(os.path.join(ROOT, "tests", "fixtures", "pgg_list.html"), encoding="utf-8") as f:
        return f.read()


def _parse():
    return PggSource(CFG).parse(_fixture(), base_url=CFG["list_url"])


def test_pgg_parser_finds_rows():
    items = _parse()
    assert len(items) == 3


def test_pgg_fields():
    first = _parse()[0]
    assert first.zrodlo == "pgg"
    # numer postępowania zostaje w tytule — to on odróżnia wpisy (url = lista)
    assert first.tytul.startswith("4926")
    assert first.zamawiajacy.startswith("Polska Grupa Górnicza S.A.")
    assert "KWK Sośnica" in first.zamawiajacy
    assert first.data_publikacji == "2026-11-06"
    assert first.termin_skladania == "2026-12-10"
    assert first.url == CFG["list_url"]


def test_pgg_dates_are_converted_from_dd_mm_yyyy():
    assert _iso_date("06.11.2026") == "2026-11-06"
    assert _iso_date("1.2.2026") is None      # PGG zawsze daje dwucyfrowe
    assert _iso_date("") is None
    assert _iso_date("2026-11-06") is None    # inny format = brak terminu


def test_pgg_rows_without_enough_cells_are_skipped():
    html = "<table><tbody><tr><td>1</td><td>Tylko dwie komórki</td></tr></tbody></table>"
    assert PggSource(CFG).parse(html) == []


def test_pgg_token_is_read_from_meta_or_hidden_input():
    meta = '<meta name="csrf-token" content="abc123">'
    hidden = '<form><input type="hidden" name="_token" value="xyz789"></form>'
    assert PggSource._token(meta) == "abc123"
    assert PggSource._token(hidden) == "xyz789"
    assert PggSource._token("<html></html>") is None


def test_pgg_is_in_build_sources():
    from scraper.run import build_sources

    assert "pgg" in [s.name for s in build_sources()]
