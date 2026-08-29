"""Testy adaptera BZP / e-Zamówienia (krok 0.2, fixture tests/fixtures/bzp_notices.json)."""
import json
import os

from scraper.sources.bzp import BzpSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPV = ["71200000", "71220000", "71221000", "71222000", "71240000",
       "71300000", "71320000", "71400000", "71248000"]


def _fixture():
    with open(os.path.join(ROOT, "tests", "fixtures", "bzp_notices.json"), encoding="utf-8") as f:
        return json.load(f)


def _source(cpv=None):
    return BzpSource({"url": "https://ezamowienia.gov.pl/mo-board/api/v1/notice",
                      "notice_type": "ContractNotice", "page_size": 100,
                      "max_pages": 8, "days_back": 1, "enabled": True},
                     cpv_codes=cpv if cpv is not None else CPV)


def _items(cpv=None):
    return _source(cpv).parse(_fixture())


def test_local_cpv_filter_drops_non_71():
    """Rekordy bez CPV 71* są odfiltrowane lokalnie (API nie filtruje)."""
    items = _items()
    assert len(items) == 2, "fixture ma 2 rekordy z CPV 71* i 1 bez — bez filtra zostają 2"
    assert all(i.zrodlo == "bzp" for i in items)


def test_no_filter_returns_all():
    items = _items(cpv=[])
    assert len(items) == 3


def test_titles_and_buyers():
    items = _items()
    assert all(i.tytul and i.zamawiajacy for i in items)


def test_deadline_present():
    items = _items()
    assert all(i.termin_skladania for i in items), "submittingOffersDate -> termin składania"
    assert all("T" in i.termin_skladania for i in items)


def test_urls_are_canonical_mp_client():
    items = _items()
    assert all("/mp-client/search/list/" in i.url for i in items)


def test_cpv_parsed():
    items = _items()
    assert all(i.cpv for i in items)
    # każde ogłoszenie ma PEŁNĄ listę swoich kodów CPV, z których co najmniej
    # jeden należy do 71* (warunek filtra lokalnego)
    assert all(any(c.split("-")[0] in CPV for c in i.cpv) for i in items)


def test_opis_stripped_from_html_body():
    items = _items()
    assert all(i.opis and "<" not in i.opis for i in items)
    assert all(i.status_opisu == "pobrany" for i in items)
    assert all(len(i.opis) <= 2000 for i in items)


def test_publication_date():
    items = _items()
    assert all((i.data_publikacji or "")[:4] == "2026" for i in items)


def test_disabled_raises():
    src = BzpSource({"enabled": False}, cpv_codes=CPV)
    try:
        src.fetch()
        assert False, "disabled source powinno rzucić"
    except RuntimeError:
        pass


# ---------- przewijanie From (offline, bez sieci) ----------

def _mk_notice(i: int, seed: float) -> dict:
    """Syntetyczne ogłoszenie o unikalnym URL-u zależnym od (seed, i)."""
    return {
        "orderObject": f"Testowe ogłoszenie nr {seed:.0f}-{i}",
        "cpvCode": "71220000-6 (Usługi projektowania architektonicznego)",
        "organizationName": "ORG",
        "publicationDate": f"2026-08-28T0{i % 10}:00:00Z",
        "submittingOffersDate": "2026-09-14T08:00:00Z",
        "htmlBody": f"<html><body><p>treść {i}</p></body></html>",
        "tenderId": f"ocds-148610-test-{seed:.0f}-{i}",
        "bzpNumber": f"2026/BZP 9{seed:.0f}{i:04d}",
    }


def _batch(start_index: int, count: int, base_dt) -> list[dict]:
    """Paczka ogłoszeń: unikalne bzpNumber, daty malejco co 2 min od base_dt."""
    from datetime import timedelta

    out = []
    for i in range(count):
        t = base_dt - timedelta(minutes=2 * (start_index + i + 1))
        n = _mk_notice(start_index + i, 7.0)
        n["publicationDate"] = t.isoformat().replace("+00:00", "Z")
        out.append(n)
    return out


def test_fetch_scrolls_from_on_cap(monkeypatch):
    """Pełna paczka -> przewinięcie From na najstarszą publikację paczki."""
    from datetime import datetime, timedelta, timezone

    src = _source()
    now = datetime.now(timezone.utc)
    calls: list[datetime] = []

    def fake_get_page(frm, to):
        calls.append(frm)
        if len(calls) == 1:
            return _batch(0, src.page_size, now)
        return _batch(src.page_size, 5, now)

    monkeypatch.setattr(src, "_get_page", fake_get_page)
    items = src.fetch()
    assert len(calls) == 2
    assert len(items) == src.page_size + 5
    # drugie zapytanie: From = najstarsza publikacja paczki 1 + 1 s
    oldest = now - timedelta(minutes=2 * src.page_size)
    assert calls[1] == oldest + timedelta(seconds=1)


def test_fetch_stops_when_no_new_items(monkeypatch):
    """Powtórzona (zbuforowana) paczka przerywa pętlę bez nieskończonej rekurencji."""
    from datetime import datetime, timedelta, timezone

    src = _source()
    now = datetime.now(timezone.utc)
    calls: list[datetime] = []

    def fake_get_page(frm, to):
        calls.append(frm)
        return _batch(0, src.page_size, now)  # zawsze ta sama paczka

    monkeypatch.setattr(src, "_get_page", fake_get_page)
    items = src.fetch()
    assert len(calls) == 2, "druga paczka bez nowych pozycji -> stop"
    assert len(items) == src.page_size


def test_fetch_single_partial_batch(monkeypatch):
    from datetime import datetime, timedelta, timezone

    src = _source()
    now = datetime.now(timezone.utc)
    calls: list[datetime] = []

    def fake_get_page(frm, to):
        calls.append(frm)
        return _batch(0, 10, now)

    monkeypatch.setattr(src, "_get_page", fake_get_page)
    items = src.fetch()
    assert len(calls) == 1
    assert len(items) == 10


def test_fetch_respects_request_budget(monkeypatch):
    """Zawsze pełne, świeże paczki -> pętla kończy się po max_requests."""
    from datetime import datetime, timedelta, timezone

    src = BzpSource({"enabled": True, "page_size": 500, "max_requests": 3,
                     "days_back": 1}, cpv_codes=CPV)
    now = datetime.now(timezone.utc)
    calls: list[datetime] = []

    def fake_get_page(frm, to):
        calls.append(frm)
        # paczki łańcuchowe: każda kolejna starsza o 4 h, wszystkie w oknie 24 h
        # i z unikalnymi bzpNumber -> pętlę przerywa wyłącznie budżet zapytań
        idx = len(calls)
        out = []
        for i in range(src.page_size):
            n = _mk_notice(idx * 1000 + i, 7.0)
            n["bzpNumber"] = f"2026/BZP {idx:04d}{i:04d}"  # unikalne między paczkami
            # daty zawsze >= frm (jak w realnym API: wyniki od From w górę),
            # malejco co 6 s -> 500 elementów mieści się w ~50 min
            n["publicationDate"] = (frm + timedelta(seconds=3600 - 6 * i)).isoformat().replace("+00:00", "Z")
            out.append(n)
        return out

    monkeypatch.setattr(src, "_get_page", fake_get_page)
    src.fetch()
    assert len(calls) == 3