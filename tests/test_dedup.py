"""Testy dedup i parsowania PHN (kroki A5, A6)."""
import json
import os
from datetime import date

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


def _buyer(url, title, buyer="Górnośląskie Centrum Medyczne"):
    a = _ann(url, title)
    a.zamawiajacy = buyer
    a.zrodlo = "ted"
    return a


def test_secondary_dedup_same_title_different_urls():
    """TED: ogłoszenie + korekta (różne numery publikacji, ten sam tytuł) = jedno."""
    a1 = _buyer("https://ted/111-2026", "Wykonanie dokumentacji projektowej")
    a2 = _buyer("https://x/t2", "Wykonanie dokumentacji projektowej")
    out = merge([a1], [a2], history_days=90)
    assert len(out) == 1


def test_secondary_dedup_keeps_extended_deadline():
    """Korekta TED przedłuża termin -> zostaje wersja z PÓŹNIEJSZYM terminem."""
    a1 = _buyer("https://ted/591163-2026", "Ten sam tytuł")
    a1.termin_skladania = "2026-09-04T08:00:00+02:00"
    a2 = _buyer("https://ted/595865-2026", "Ten sam tytuł")
    a2.termin_skladania = "2026-09-08T08:00:00+02:00"
    out = merge([], [a1, a2], history_days=90)
    assert len(out) == 1
    assert out[0].termin_skladania == "2026-09-08T08:00:00+02:00"


def test_secondary_dedup_store_keeps_newer_correction():
    """Scenariusz realny (595865-2026): stara wersja w magazynie, korekta
    przychodzi w incoming — magazyn dostaje nowszy numer publikacji."""
    old = _buyer("https://ted/591163-2026", "Ten sam tytuł")
    old.termin_skladania = "2026-09-04T08:00:00+02:00"
    old.data_publikacji = "2026-08-27"
    corr = _buyer("https://ted/595865-2026", "Ten sam tytuł")
    corr.termin_skladania = "2026-09-08T08:00:00+02:00"
    corr.data_publikacji = "2026-08-28"
    out = merge([old], [corr], history_days=90)
    assert len(out) == 1
    assert out[0].url == "https://ted/595865-2026"


def test_secondary_dedup_dated_beats_undated():
    """Egzemplarz z terminem wygrywa z egzemplarzem bez terminu."""
    a1 = _buyer("https://x/nodaterm", "Ten sam tytuł")
    a1.data_publikacji = "2026-08-29"  # nowsza publikacja, ale bez terminu
    a2 = _buyer("https://x/withterm", "Ten sam tytuł")
    a2.termin_skladania = "2026-09-01"
    out = merge([], [a1, a2], history_days=90)
    assert len(out) == 1
    assert out[0].url == "https://x/withterm"


def test_secondary_dedup_keeps_different_sources():
    """Ten sam tytuł z różnych źródeł NIE jest scalany."""
    a_ted = _buyer("https://x/ted", "Ten sam tytuł")
    a_ted.zrodlo = "ted"
    a_pz = _buyer("https://x/pz", "Ten sam tytuł")
    a_pz.zrodlo = "pz-search"
    out = merge([], [a_ted, a_pz], history_days=90)
    assert len(out) == 2


def test_no_secondary_dedup_without_buyer():
    """Bez zamawiającego dedup wtórny nie zadziała (za ostrożne scalanie)."""
    a1, a2 = _ann("https://x/1", "Ten sam tytuł"), _ann("https://x/2", "Ten sam tytuł")
    out = merge([], [a1, a2], history_days=90)
    assert len(out) == 2


def test_phn_page_url_pagination():
    src = PhnSource({"list_url": "https://bip.phnsa.pl/ogloszenia/1", "crawl_delay": 10, "pages": 3})
    assert src._page_url(1) == "https://bip.phnsa.pl/ogloszenia/1"
    assert src._page_url(2) == "https://bip.phnsa.pl/ogloszenia/2"
    assert src._page_url(3) == "https://bip.phnsa.pl/ogloszenia/3"


def test_new_item_gets_dodano():
    """Nowe ogłoszenie dostaje datę pierwszego dodania (licznik „dodane w dniu X”)."""
    out = merge([], [_ann("https://x/new", "świeży")], history_days=90)
    assert out[0].dodano == date.today().isoformat()


def test_existing_item_keeps_dodano():
    """Powtórne pobranie tego samego ogłoszenia NIE zmienia daty dodania."""
    old = _ann("https://x/1", "A")
    old.dodano = "2026-08-20"
    out = merge([old], [_ann("https://x/1", "A")], history_days=90)
    assert len(out) == 1
    assert out[0].dodano == "2026-08-20"


def test_secondary_dedup_preserves_original_dodano():
    """Korekta (nowszy termin) wygrywa, ale zachowuje pierwotną datę dodania —
    licznik dnia nie zlicza korekty jako „nowego” ogłoszenia."""
    old = _buyer("https://ted/591163-2026", "Ten sam tytuł")
    old.termin_skladania = "2026-09-04T08:00:00+02:00"
    old.dodano = "2026-08-20"
    corr = _buyer("https://ted/595865-2026", "Ten sam tytuł")
    corr.termin_skladania = "2026-09-08T08:00:00+02:00"
    out = merge([old], [corr], history_days=90)
    assert len(out) == 1
    assert out[0].url == "https://ted/595865-2026"
    assert out[0].dodano == "2026-08-20"

