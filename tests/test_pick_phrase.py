"""Wybór frazy pz-search: cron → fraza, odporny na opóźnienie GitHuba.

Stary wybór po godzinie startu (`hour - 5`) rozjeżdżał się przy opóźnionych
cronach: run o 15:00 zamiast 07:00 brał frazę slotu 10:07, więc jedna fraza
wypadała dwa razy, a inna wcale — pomiar per fraza pokazywał fałszywe zera.
"""
from datetime import date

import yaml

from scraper.pick_phrase import choose, phrase_for_day, phrase_for_schedule
from scraper.run import load_yaml

CFG = {
    "phrases": ["a", "b", "c"],
    "slots": [
        {"cron": "7 5 * * *", "phrase": "dokumentacja wielobranżowa"},
        {"cron": "7 7 * * *", "phrase": "dokumentacja projektowa"},
    ],
}


def test_slot_is_chosen_by_the_cron_that_fired():
    assert phrase_for_schedule(CFG, "7 5 * * *") == "dokumentacja wielobranżowa"
    assert phrase_for_schedule(CFG, "7 7 * * *") == "dokumentacja projektowa"


def test_a_delayed_run_keeps_its_slot_phrase():
    """Opóźnienie zmienia godzinę startu, ale nie cron, który odpalił run."""
    assert phrase_for_schedule(CFG, "7 5 * * *") == "dokumentacja wielobranżowa"


def test_cron_matching_tolerates_extra_spaces():
    assert phrase_for_schedule(CFG, "  7   5 * * *  ") == "dokumentacja wielobranżowa"


def test_dispatch_without_a_schedule_falls_back_to_the_daily_rotation():
    assert phrase_for_schedule(CFG, None) is None
    assert choose(CFG, None, None, day=date(2026, 11, 7)) == "b"


def test_an_explicit_phrase_wins_over_the_schedule():
    assert choose(CFG, "7 5 * * *", "koncepcja") == "koncepcja"


def test_unknown_schedule_falls_back_to_the_daily_rotation():
    assert choose(CFG, "0 3 * * *", None, day=date(2026, 11, 6)) == "a"


def test_daily_rotation_without_phrases_is_empty():
    assert phrase_for_day({}) is None


def test_configured_slots_match_the_workflow_crons():
    """Każdy cron z pz_search.yml ma frazę w configu i odwrotnie (6 slotów)."""
    cfg = load_yaml("sources.yaml")["platformazakupowa_search"]
    with open(".github/workflows/pz_search.yml", encoding="utf-8") as f:
        import re

        crons = re.findall(r"^\s+- cron: '([^']+)'", f.read(), re.M)
    assert len(crons) == 6
    assert [s["cron"] for s in cfg["slots"]] == crons
    # frazy slotów są podzbiorem listy rotacyjnej — inaczej dispatch bez frazy
    # mógłby wybrać coś, czego nie ma w harmonogramie
    assert {s["phrase"] for s in cfg["slots"]} <= set(cfg["phrases"])
    assert [s["phrase"] for s in cfg["slots"]] == cfg["phrases"]
