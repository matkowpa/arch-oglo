"""Testy silnika scoringowego (krok A2 final_plan.md)."""
from scraper.model import Announcement


EML_TITLE = (
    "Wykonanie szczegółowej, wielobranżowej dokumentacji projektowo-kosztorysowej "
    "dla obiektu sanatoryjnego w Kołobrzegu"
)


def test_eml_title_publishes(scorer):
    """Tytuł z przykład_przetargu.eml -> oczekiwany wynik: publikacja."""
    a = scorer.score(Announcement(zrodlo="t", tytul=EML_TITLE, url="https://x/1"))
    assert a.score >= 3
    assert scorer.should_publish(a)


def test_exception_infra_not_penalized(scorer):
    """„wraz z niezbędną infrastrukturą" NIE może wykluczyć ogłoszenia."""
    a = scorer.score(Announcement(
        zrodlo="t",
        tytul="Dokumentacja projektowa budynku biurowego",
        url="https://x/2",
        opis="Rozbudowa budynku biurowego wraz z niezbędną infrastrukturą "
             "techniczną pochodzenia węglowego oraz projektowanie architektoniczne wnętrz.",
    ))
    assert "infrastruktura" not in a.tagi
    assert scorer.should_publish(a)


def test_infra_penalized_without_exception(scorer):
    a = scorer.score(Announcement(
        zrodlo="t",
        tytul="Prace projektowe w zakresie sieci kanalizacyjnej osiedla",
        url="https://x/3",
    ))
    assert "infrastruktura" in a.tagi
    assert not scorer.should_publish(a)


def test_road_penalized(scorer):
    a = scorer.score(Announcement(
        zrodlo="t", tytul="Prace projektowe w zakresie drogowego odcinka autostrady",
        url="https://x/4",
    ))
    assert not scorer.should_publish(a)


def test_samorzad_lowered_not_removed(scorer):
    base = Announcement(zrodlo="t", tytul="Prace projektowe w zakresie budynku",
                        url="https://x/5", zamawiajacy="Urząd Miasta")
    scored = scorer.score(base)
    assert "samorząd" in scored.tagi
    assert scored.score >= 2  # 3 (hard) - 1 (samorząd)


def test_konkurs_lower_than_dokumentacja(scorer):
    a = scorer.score(Announcement(zrodlo="t", tytul="Konkurs architektoniczny na koncepcję muzeum",
                                  url="https://x/6"))
    assert a.score == 2  # +2 (konkurs, jednokrotnie wg planu)
    assert "konkurs" in a.tagi


def test_sp_company_bonus(scorer):
    a = scorer.score(Announcement(
        zrodlo="t", tytul="Prace projektowe w zakresie magazynu",
        url="https://x/7", zamawiajacy="Polski Holding Nieruchomości S.A."))
    assert "spolka-sp" in a.tagi
    assert a.score >= 4  # 3*2 - wait: hard+3 x2=6 +1 sp = 7


def test_cpv_bonus(scorer):
    a = scorer.score(Announcement(zrodlo="t", tytul="Zaproszenie do ofert", url="https://x/8",
                                  cpv=["71220000-2"]))
    assert a.score == 3
    assert "cpv-71" in a.tagi


def test_brak_terminu_tag(scorer):
    a = scorer.score(Announcement(zrodlo="t", tytul="Dokumentacja wielobranżowa hali",
                                  url="https://x/9", termin_skladania=None))
    assert "brak-terminu" in a.tagi
