"""Testy parsera KGHM (kghm.com/przetargi-nieograniczone) — wyłącznie na fixture."""
import os

from scraper.sources.bip.kghm import KghmSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CFG = {"list_url": "https://kghm.com/pl/przetargi-nieograniczone", "crawl_delay": 10, "pages": 2}


def _parse_fixture():
    fixture = os.path.join(ROOT, "tests", "fixtures", "kghm_przetargi.html")
    with open(fixture, encoding="utf-8") as f:
        html = f.read()
    return KghmSource(CFG).parse(html, base_url=CFG["list_url"])


def test_kghm_parser_finds_rows():
    items = _parse_fixture()
    assert items, "parser nie znalazł ogłoszeń na fixture KGHM"
    assert len(items) >= 10  # 10 wierszy/stronę


def test_kghm_fields():
    first = _parse_fixture()[0]
    assert first.zrodlo == "bip:kghm"
    assert first.tytul
    assert first.zamawiajacy == "KGHM Polska Miedź S.A."
    assert first.data_publikacji and len(first.data_publikacji) == 10  # ISO date
    assert first.termin_skladania  # ISO datetime z <time datetime>
    assert first.url.startswith("https://kghm.com/pl/")  # urljoin z href względnego


def test_kghm_pagination_url():
    src = KghmSource(CFG)
    assert src._page_url(1) == "https://kghm.com/pl/przetargi-nieograniczone"
    assert src._page_url(2) == "https://kghm.com/pl/przetargi-nieograniczone?page=1"
    assert src._page_url(3) == "https://kghm.com/pl/przetargi-nieograniczone?page=2"


def test_kghm_empty_table():
    assert KghmSource(CFG).parse("<html><body>brak tabeli</body></html>") == []


def test_kghm_in_build_sources():
    from scraper.run import build_sources

    names = [s.name for s in build_sources()]
    assert "bip:kghm" in names


def test_kghm_side_sections_without_a_deadline_column():
    """„Pozostałe ogłoszenia"/„Umowy ramowe": data jako tekst, brak terminu.

    Dodane 2026-11-06 — te sekcje mają inne kolumny niż spis przetargów:
    zamiast `<time datetime>` jest gołe `YYYY-MM-DD` i nie ma terminu ofert.
    """
    fixture = os.path.join(ROOT, "tests", "fixtures", "kghm_pozostale.html")
    with open(fixture, encoding="utf-8") as f:
        html = f.read()
    items = KghmSource({**CFG, "sections": []}).parse(html, base_url=CFG["list_url"])
    assert len(items) == 2
    assert items[0].data_publikacji == "2025-06-04"
    assert items[0].termin_skladania is None
    assert items[0].url.startswith("https://kghm.com/pl/postepowanie")


def test_kghm_fetches_the_main_list_and_every_section():
    cfg = {**CFG, "sections": [{"url": "https://kghm.com/pl/a", "pages": 2},
                               "https://kghm.com/pl/b"]}
    pages = [(base, n) for base, n in KghmSource(cfg)._targets()]
    assert pages == [("https://kghm.com/pl/przetargi-nieograniczone", 2),
                     ("https://kghm.com/pl/a", 2),
                     ("https://kghm.com/pl/b", 1)]
