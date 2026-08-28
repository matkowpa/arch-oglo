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


def test_prune_undated_ted():
    old = _ann("https://x/old", "bez daty")
    old.zrodlo = "ted"
    old.termin_skladania = None
    old.data_publikacji = None
    fresh = _ann("https://x/new", "świeży")
    fresh.termin_skladania = "2026-09-14 09:00:00"
    out = merge([old], [fresh], history_days=90, prune_undated=("ted",))
    assert [a.url for a in out] == ["https://x/new"]


def test_prune_undated_only_for_selected_source():
    old_pz = _ann("https://x/pz", "pz bez daty")
    old_pz.zrodlo = "pz-search"
    old_pz.termin_skladania = None
    old_pz.data_publikacji = None
    fresh = _ann("https://x/new", "świeży")
    fresh.termin_skladania = "2026-09-14 09:00:00"
    out = merge([old_pz], [fresh], history_days=90, prune_undated=("ted",))
    assert {a.url for a in out} == {"https://x/new", "https://x/pz"}


def test_merge_fills_termin_on_repeat():
    old = _ann("https://x/1", "A")
    old.termin_skladania = None
    new = _ann("https://x/1", "A")
    new.termin_skladania = "2026-09-14 09:00:00"
    out = merge([old], [new], history_days=90)
    assert out[0].termin_skladania == "2026-09-14 09:00:00"
