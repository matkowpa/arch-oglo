"""Testy parsera PSE (platforma eB2B, przetargi.pse.pl) — wyłącznie na fixture."""
import json
import os

from scraper.sources.bip.pse import PseSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CFG = {
    "list_url": "https://przetargi.pse.pl/open-auctions.html",
    "api_url": "https://przetargi.pse.pl/auction/auction/list",
}


def _load_fixture() -> dict:
    fixture = os.path.join(ROOT, "tests", "fixtures", "pse_open_auctions.json")
    with open(fixture, encoding="utf-8") as f:
        return json.load(f)


def _parse():
    return PseSource(CFG).parse(_load_fixture())


def test_pse_parse_rows():
    items = _parse()
    assert items, "parser nie znalazł ogłoszeń w fixture PSE"
    assert len(items) == len(_load_fixture()["data"])


def test_pse_fields():
    items = _parse()
    first = items[0]
    assert first.zrodlo == "bip:pse"
    assert first.tytul
    assert "ELEKTROENERGETYCZNE" in first.zamawiajacy.upper()
    # szczegóły za loginem — url = strona listy (sonda 2026-09-03)
    assert first.url == CFG["list_url"]
    assert first.data_publikacji and len(first.data_publikacji) == 10
    assert first.status_opisu == "brak"


def test_pse_termin_offers_deadline():
    """Wiersz 'Etap Oferty' -> termin = offers_attachments_deadline_date."""
    data = _load_fixture()
    row = next(r for r in data["data"] if r.get("offers_attachments_deadline_date"))
    items = PseSource(CFG).parse({"data": [row]})
    assert items[0].termin_skladania == row["offers_attachments_deadline_date"]


def test_pse_termin_fallback_stage_offers_end():
    """Brak offers_attachments_deadline_date -> fallback stage_offers_end_date."""
    row = {"name": "Etap ofert bez pola deadline", "is_test": False,
           "company_name": "POLSKIE SIECI ELEKTROENERGETYCZNE S.A.",
           "publication_date": "2026-09-01 08:00:00",
           "offers_attachments_deadline_date": None,
           "stage_offers_end_date": "2026-09-30 15:00:00"}
    items = PseSource(CFG).parse({"data": [row]})
    assert items[0].termin_skladania == "2026-09-30 15:00:00"


def test_pse_rfi_without_termin():
    """Etap RFI bez żadnego terminu ofert -> termin_skladania None (tag brak-terminu)."""
    data = _load_fixture()
    row = next(r for r in data["data"]
               if not r.get("offers_attachments_deadline_date")
               and not r.get("stage_offers_end_date"))
    items = PseSource(CFG).parse({"data": [row]})
    assert items[0].termin_skladania is None


def test_pse_skips_test_rows_and_empty_names():
    data = {"data": [
        {"name": "Postępowanie testowe", "is_test": True},
        {"name": "   ", "is_test": False},
        {"name": "Zwykłe postępowanie", "is_test": False,
         "company_name": "POLSKIE SIECI ELEKTROENERGETYCZNE S.A.",
         "publication_date": "2026-09-01 10:00:00",
         "offers_attachments_deadline_date": "2026-10-01 10:00:00"},
    ]}
    items = PseSource(CFG).parse(data)
    assert len(items) == 1
    assert items[0].tytul == "Zwykłe postępowanie"
    assert items[0].termin_skladania == "2026-10-01 10:00:00"


def test_pse_empty():
    assert PseSource(CFG).parse({"data": []}) == []


def test_pse_distinct_hashes():
    items = _parse()
    hashes = {i.hash for i in items}
    assert len(hashes) == len(items)  # różne tytuły -> różne hashe mimo wspólnego URL


def test_pse_in_build_sources():
    from scraper.run import build_sources

    names = [s.name for s in build_sources()]
    assert "bip:pse" in names
