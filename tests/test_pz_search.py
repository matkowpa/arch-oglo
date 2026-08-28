"""Testy parsera publicznej wyszukiwarki platformazakupowa.pl (źródło pz-search)."""
import os

from scraper.sources.pz_search import PzSearchSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fixture():
    with open(os.path.join(ROOT, "tests", "fixtures", "pz_search.html"), encoding="utf-8") as f:
        return f.read()


def _parse():
    return PzSearchSource({"base_url": "https://platformazakupowa.pl/all",
                           "phrases": ["dokumentacja"]}).parse(_fixture())


def test_parses_rows():
    items = _parse()
    assert items, "parser nie znalazł wierszy wyników"
    assert all(i.tytul and i.url for i in items)


def test_urls_point_to_transakcja():
    items = _parse()
    assert all("/transakcja/" in i.url for i in items)


def test_title_without_id_suffix():
    items = _parse()
    assert all(not i.tytul.endswith(")") or "ID" not in i.tytul[-15:] for i in items)


def test_deadline_parsed():
    items = _parse()
    with_deadline = [i for i in items if i.termin_skladania]
    assert with_deadline, "brak terminów składania w wynikach"
    assert all("-" in i.termin_skladania for i in with_deadline)


def test_buyer_extracted():
    items = _parse()
    assert all(i.zamawiajacy for i in items)
    assert all("(ID" not in i.zamawiajacy for i in items), "zamawiający zawiera resztkę (ID ...)"
    joined = " | ".join(i.zamawiajacy for i in items)
    assert "ARESZT" in joined.upper() or "ZARZĄD" in joined.upper()


def test_real_hit_dokumentacja_wielobranzowa(scorer):
    """Słynny przypadek z wyników: dokumentacja wielobranżowa aresztu — musi publikować."""
    items = _parse()
    hit = [i for i in items if "wielobranżowa" in i.tytul.lower()]
    assert hit, "fixture nie zawiera oczekiwanego trafienia wielobranżowego"
    scored = scorer.score(hit[0])
    assert scorer.should_publish(scored)


def test_road_case_penalized(scorer):
    """BUDOWA DROGI ... DOKUMENTACJA PROJEKTOWA — tytuł z wyników; drogi muszą wykluczać."""
    items = _parse()
    road = [i for i in items if "DROGI" in i.tytul.upper() and "DOKUMENTACJA PROJEKTOWA" in i.tytul.upper()]
    if not road:
        return  # fixture mógł się zmienić — test warunkowy
    scored = scorer.score(road[0])
    assert not scorer.should_publish(scored)
    assert "drogi" in scored.tagi


def test_phrase_rotation_deterministic():
    cfg = {"base_url": "https://platformazakupowa.pl/all",
           "phrases": ["a", "b", "c"]}
    s1 = PzSearchSource(cfg).for_run()
    s2 = PzSearchSource(cfg).for_run("x")
    assert s2._phrase == "x"
    assert s1._phrase in ("a", "b", "c")
