"""Dedup po hash(url+tytuł) + historia 90 dni (sekcja 8.1).

Dodatkowy dedup wtórny: to samo ogłoszenie (ten sam źródło + znormalizowany
tytuł + zamawiający) z różnych URL-i (np. TED: ogłoszenie + korekta, inne
numery publikacji) liczone jest raz — zostaje NAJNOWSZY egzemplarz
(późniejszy termin składania / data publikacji; korekty TED przedłużają
termin, więc stara wersja jest nieważna).
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta

from .model import Announcement


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def load_existing(path: str) -> list[Announcement]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [Announcement.from_dict(d) for d in json.load(f)]


def merge(existing: list[Announcement], incoming: list[Announcement],
          history_days: int = 90, prune_undated: tuple[str, ...] = ()) -> list[Announcement]:
    by_hash = {a.hash: a for a in existing}
    for a in incoming:
        if a.hash in by_hash:
            # zachowaj pierwszy egzemplarz, uzupełnij brakujące pola (np. opis)
            old = by_hash[a.hash]
            if old.opis in (None, "") and a.opis:
                old.opis, old.status_opisu = a.opis, a.status_opisu
            if old.termin_skladania in (None, "") and a.termin_skladania:
                old.termin_skladania = a.termin_skladania
        else:
            by_hash[a.hash] = a

    cutoff = (date.today() - timedelta(days=history_days)).isoformat()
    out = []
    for a in by_hash.values():
        d = a.data_publikacji or a.termin_skladania or ""
        # ogłoszenia bez żadnej daty trzymamy 1 run dłużej — usunie je krok 8.6/archiwum
        if d and d[:10] < cutoff:
            continue
        if not d and a.zrodlo in prune_undated:
            # źródło (TED) teraz zwraca wyłącznie wpisy z terminem — stare śmieci bez daty usuwamy
            continue
        out.append(a)
    out.sort(key=lambda x: (x.termin_skladania or "9999", x.tytul))

    # dedup wtórny: ten sam zrodlo + tytuł + zamawiający z różnych URL-i
    # (np. TED: ogłoszenie + korekta, inne numery publikacji) liczone raz.
    # Zostaje NAJNOWSZA wersja: późniejszy termin składania (korekty TED
    # przedłużają termin — stara wersja jest nieważna), remis -> późniejsza
    # data publikacji. Bez zamawiającego dedup wtórny nie zadziała
    # (za ostrożne scalanie).
    def _rank(a: Announcement) -> tuple:
        return (a.termin_skladania or "", a.data_publikacji or "")

    best: dict = {}
    final: list[Announcement] = []
    for a in out:
        if not a.zamawiajacy:
            final.append(a)
            continue
        key = (a.zrodlo, _norm(a.tytul), _norm(a.zamawiajacy))
        cur = best.get(key)
        if cur is None or _rank(a) > _rank(cur):
            best[key] = a
    final.extend(best.values())
    final.sort(key=lambda x: (x.termin_skladania or "9999", x.tytul))
    return final


def save(path: str, items: list[Announcement]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([a.to_dict() for a in items], f, ensure_ascii=False, indent=1)
