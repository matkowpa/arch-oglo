"""Dedup po hash(url+tytuł) + historia 90 dni (sekcja 8.1)."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

from .model import Announcement


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
    return out


def save(path: str, items: list[Announcement]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([a.to_dict() for a in items], f, ensure_ascii=False, indent=1)
