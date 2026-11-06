"""Healthcheck: scalanie runów w pliku dnia + metryka lejka.

Plik `data/history/<dzień>.json` jest wspólny dla daily i 6 runów pz-search, a
workflow commituje go z `-X theirs` — czyli każdy kolejny run nadpisywał
poprzedni i historia pokazywała tylko ostatnią frazę (zwykle 0 wyników).
"""
import json

from scraper import healthcheck as hc


def _write(history, day, data):
    (history / f"{day}.json").write_text(json.dumps(data), encoding="utf-8")


def test_second_run_of_the_day_is_merged_not_overwritten(tmp_path):
    hc.record_run(str(tmp_path), {"pz-search": {"ok": True, "count": 2, "kept": 1}})
    hc.record_run(str(tmp_path), {"pz-search": {"ok": True, "count": 3, "kept": 2}})
    saved = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert saved["pz-search"] == {"ok": True, "count": 5, "kept": 3, "runs": 2}


def test_a_failed_run_marks_the_day_as_failed(tmp_path):
    hc.record_run(str(tmp_path), {"ted": {"ok": True, "count": 10, "kept": 4}})
    hc.record_run(str(tmp_path), {"ted": {"ok": False, "count": 0, "kept": 0}})
    saved = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert saved["ted"]["ok"] is False
    assert saved["ted"]["count"] == 10  # udane pobranie z pierwszego runu zostaje


def test_a_source_missing_from_the_second_run_keeps_its_entry(tmp_path):
    hc.record_run(str(tmp_path), {"bzp": {"ok": True, "count": 36, "kept": 13}})
    hc.record_run(str(tmp_path), {"ted": {"ok": True, "count": 439, "kept": 133}})
    saved = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert saved["bzp"] == {"ok": True, "count": 36, "kept": 13, "runs": 1}
    assert saved["ted"]["count"] == 439


def test_yield_drop_is_measured_per_run_not_per_day(tmp_path):
    # poprzednie dni: 6 runów × 2 pozycje = 12 w pliku dnia
    for day in ("2026-08-01", "2026-08-02"):
        _write(tmp_path, day, {"pz-search": {"ok": True, "count": 12, "kept": 1, "runs": 6}})
    # dziś 3 runy × 2 = 6 pozycji: suma niższa, ale wynik/run identyczny
    today = {"pz-search": {"ok": True, "count": 6, "kept": 1, "runs": 3}}
    assert not [x for x in hc.check(str(tmp_path), today) if "yield dropped" in x]

    # 3 runy × 1 = 1/run wobec 2/run -> warning
    today = {"pz-search": {"ok": True, "count": 3, "kept": 0, "runs": 3}}
    lines = hc.check(str(tmp_path), today)
    assert any("yield dropped" in x and "1/run vs avg 2.0/run" in x for x in lines)


def test_source_that_fetches_but_never_publishes_is_reported(tmp_path):
    for day in ("2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"):
        _write(tmp_path, day, {"bip:kghm": {"ok": True, "count": 20, "kept": 0, "runs": 1}})
    lines = hc.check(str(tmp_path), {"bip:kghm": {"ok": True, "count": 20, "kept": 0}})
    assert any("bip:kghm" in x and "published 0 of 100" in x for x in lines)


def test_legacy_history_without_kept_does_not_crash(tmp_path):
    _write(tmp_path, "2026-08-01", {"ted": {"ok": True, "count": 400}})
    lines = hc.check(str(tmp_path), {"ted": {"ok": True, "count": 439, "kept": 133}})
    assert not [x for x in lines if "published 0 of" in x]


def test_unreachable_source_is_an_error(tmp_path):
    lines = hc.check(str(tmp_path), {"bzp": {"ok": False, "count": 0, "kept": 0}})
    assert "::error::source bzp unreachable/unparsed" in lines
