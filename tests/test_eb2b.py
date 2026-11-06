"""Testy instancji eB2B: PSE (bip:pse) i PHN (bip:phn-platform).

Obie firmy używają tej samej aplikacji eB2B, więc parser jest jeden
(`Eb2bSource`), a różnią je adresy i `default_buyer` z config/sources.yaml.
PHN nie wypełnia `offers_attachments_deadline_date` — termin bierzemy z końca
bieżącego etapu, inaczej wszystkie jego postępowania miałyby tag brak-terminu.
"""
import json
import os

from scraper.sources.bip.pse import Eb2bSource, PseSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PHN_CFG = {
    "id": "phn-platform",
    "list_url": "https://platformazakupowa.phnsa.pl/open-auctions.html",
    "api_url": "https://platformazakupowa.phnsa.pl/auction/auction/list",
    "default_buyer": "Polski Holding Nieruchomości S.A.",
    "crawl_delay": 10,
    "limit": 50,
    "max_requests": 2,
}


def _phn_fixture() -> dict:
    path = os.path.join(ROOT, "tests", "fixtures", "phn_eb2b_open_auctions.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_eb2b_class_is_shared_with_pse():
    assert PseSource is Eb2bSource


def test_phn_source_name_comes_from_config_id():
    """Klucz źródła = `bip:<id>`, bo `name` w configu to etykieta spółki."""
    assert Eb2bSource(PHN_CFG).name == "bip:phn-platform"
    assert Eb2bSource({"list_url": "x", "api_url": "y"}).name == "bip:pse"


def test_phn_parse_uses_its_own_buyer():
    items = Eb2bSource(PHN_CFG).parse(_phn_fixture())
    assert len(items) == 2
    assert items[0].zrodlo == "bip:phn-platform"
    assert "HOLDING NIERUCHOMOŚCI" in items[0].zamawiajacy.upper()
    assert items[0].url == PHN_CFG["list_url"]  # szczegóły za loginem


def test_phn_deadline_falls_back_to_the_current_stage_end():
    items = Eb2bSource(PHN_CFG).parse(_phn_fixture())
    row = _phn_fixture()["data"][0]
    assert items[0].termin_skladania == row["current_stage_end_time"]
    assert items[0].data_publikacji == row["publication_date"][:10]


def test_phn_is_in_build_sources_with_a_distinct_name():
    from scraper.run import build_sources

    names = [s.name for s in build_sources()]
    assert "bip:pse" in names
    assert "bip:phn-platform" in names
