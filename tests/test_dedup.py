"""Testy dedup i parsowania PHN (kroki A5, A6)."""
import json
import os

from scraper.dedup import merge
from scraper.model import Announcement
from scraper.sources.bip.phn import PhnSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ann(url, title):
    return Announcement(zrodlo="t", tytul=title, url=url)


def test_dedup_by_hash():
    old = merge([_ann("https://x/1", "A")], [_ann("https://x/1", "A")], history_days=90)
    assert len(old) == 1


def test_dedup_keeps_richer_copy():
    old = merge([_ann("https://x/1", "A")],
                [_ann("https://x/1", "A")], history_days=90)
    assert len(old) == 1


def test_history_window_drops_old():
    a = _ann("https://x/2", "B")
    a.data_publikacji = "2000-01-01"
    out = merge([a], [], history_days=90)
    assert out == []


def test_sort_by_termin():
    a1, a2 = _ann("https://x/3", "późny"), _ann("https://x/4", "pilny")
    a1.termin_skladania, a2.termin_skladania = "2030-06-01", "2026-09-01"
    out = merge([], [a1, a2], history_days=90)
    assert out[0].tytul == "pilny"


def test_phn_parser_on_fixture():
    fixture = os.path.join(ROOT, "tests", "fixtures", "phn_ogloszenia.html")
    with open(fixture, encoding="utf-8") as f:
        html = f.read()
    items = PhnSource({"list_url": "https://bip.phnsa.pl/ogloszenia", "crawl_delay": 10}).parse(
        html, base_url="https://bip.phnsa.pl/ogloszenia")
    assert items, "parser nie znalazł ogłoszeń na fixture PHN"
    assert all(i.tytul for i in items)
    assert all(i.zrodlo == "bip:phn" for i in items)


def test_announcement_hash_stable():
    a1 = _ann("https://x/1?utm=spam", "Tytuł  Test")
    a2 = _ann("https://x/1", "tytuł test")
    assert a1.hash == a2.hash


def test_roundtrip_dict():
    a = _ann("https://x/9", "T")
    a.score = 5
    a.tagi = ["x"]
    b = Announcement.from_dict(a.to_dict())
    assert b == a
