"""Model danych Announcement (sekcja 3.1 final_plan.md)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@dataclass
class Announcement:
    zrodlo: str
    tytul: str
    url: str
    zamawiajacy: str = ""
    data_publikacji: Optional[str] = None  # ISO date
    termin_skladania: Optional[str] = None  # ISO datetime/date; None -> tag brak-terminu
    opis: Optional[str] = None
    cpv: list = field(default_factory=list)
    score: int = 0
    tagi: list = field(default_factory=list)
    status_opisu: str = "brak"  # 'brak' | 'pobrany'

    @property
    def hash(self) -> str:
        raw = f"{_norm(self.url.split('?')[0])}|{_norm(self.tytul)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hash"] = self.hash
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Announcement":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known and k != "hash"})
