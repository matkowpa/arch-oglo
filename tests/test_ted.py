"""Testy parsera TED: fallback terminu dla legacy UBL (deadline-receipt-request)."""
from scraper.sources.ted import TedSource


def _src() -> TedSource:
    return TedSource({"url": "https://api.ted.europa.eu/v3/notices/search", "query": "x"})


def test_parse_termin_fallback_legacy_ubl():
    """Legacy UBL (konwersje z platform krajowych, np. BZP) ma termin tylko
    w polu `deadline-receipt-request` — bez fallbacku termin byłby None."""
    data = {"notices": [{
        "publication-number": "595865-2026",
        "notice-title": {"pol": ["Opracowanie dokumentacji projektowej"]},
        "buyer-name": {"pol": ["Uniwersytecki Szpital Kliniczny Nr 1 w Lublinie"]},
        "classification-cpv": ["71220000"],
        "publication-date": "2026-08-28+02:00",
        "deadline-receipt-request": ["2026-09-08T08:00:00+02:00"],
    }]}
    out = _src()._parse(data)
    assert len(out) == 1
    assert out[0].termin_skladania == "2026-09-08T08:00:00+02:00"
    assert "595865-2026" in out[0].url


def test_parse_termin_eforms_primary():
    """eForms: pole `deadline` ma pierwszeństwo przed fallbackiem."""
    data = {"notices": [{
        "publication-number": "1-2026",
        "notice-title": "T",
        "deadline": "2026-09-01T10:00:00+02:00",
        "deadline-receipt-request": ["2026-09-08T08:00:00+02:00"],
    }]}
    out = _src()._parse(data)
    assert out[0].termin_skladania == "2026-09-01T10:00:00+02:00"


def test_parse_no_deadline_fields():
    """Brak obu pól terminu -> None (tag brak-terminu ze scoringu)."""
    data = {"notices": [{"publication-number": "2-2026", "notice-title": "T"}]}
    out = _src()._parse(data)
    assert out[0].termin_skladania is None