"""Silnik scoringowy (sekcje 1 i 3.3 final_plan.md).

Deterministyczny: Python + regex + YAML, bez LLM. Trafienia liczone osobno na
tytule (waga x2) i opisie (x1). Wyjątek „wraz z niezbędną infrastrukturą"
blokuje kary infrastrukturalne w okolicy wystąpienia (±EXCEPTION_WINDOW znaków).
"""
from __future__ import annotations

import re
from typing import Optional

from .model import Announcement

EXCEPTION_WINDOW = 120  # znaków wokół trafienia kary — sprawdzenie frazy wyjątku


class Scorer:
    def __init__(self, keywords: dict, cpv: dict, weights: dict, sources_cfg: dict):
        self.kw = keywords
        self.cpv_codes = [str(c) for c in cpv.get("cpv", [])]
        self.w = weights.get("weights", {})
        self.sp = [s.lower() for s in sources_cfg.get("sp_companies", [])]
        self.gpw = [s.lower() for s in sources_cfg.get("exchange_companies", [])]
        self.exc = [e.lower() for e in keywords.get("exception_phrases", [])]
        self.t_publish = keywords.get("thresholds", {}).get("publish", 3)
        self.t_high = keywords.get("thresholds", {}).get("high", 5)

    # ---------- pomocnicze ----------

    @staticmethod
    def _find(text: str, phrase: str) -> list[int]:
        if not text or not phrase:
            return []
        return [m.start() for m in re.finditer(re.escape(phrase.lower()), text.lower())]

    def _exception_near(self, text: str, pos: int) -> bool:
        lo, hi = max(0, pos - EXCEPTION_WINDOW), pos + EXCEPTION_WINDOW
        window = text[lo:hi].lower()
        return any(e in window for e in self.exc)

    def _count(self, text: str, phrases: list[str], respect_exception: bool = False) -> int:
        n = 0
        for p in phrases:
            for pos in self._find(text, p):
                if respect_exception and self._exception_near(text, pos):
                    continue
                n += 1
        return n

    def _company_bonus(self, who: str) -> tuple[int, list[str]]:
        w = (who or "").lower()
        tags = []
        pts = 0
        if any(s in w for s in self.sp):
            pts += self.w.get("sp_company", 1)
            tags.append("spolka-sp")
        if any(s in w for s in self.gpw):
            pts += self.w.get("exchange_company", 1)
            tags.append("giełdowa")
        return pts, tags

    # ---------- główny scoring ----------

    def score(self, a: Announcement) -> Announcement:
        title = a.tytul or ""
        opis = a.opis or ""
        tags: list[str] = []

        hard = self.kw.get("hard", [])
        def hard_pts(text: str) -> int:
            return sum(h["score"] for h in hard for _ in self._find(text, h["phrase"]))

        pts = self.w.get("title", 2) * hard_pts(title) + self.w.get("opis", 1) * hard_pts(opis)

        if self._count(title + " " + opis, self.kw.get("contest", [])):
            pts += self.w.get("contest", 2)
            tags.append("konkurs")

        # CPV
        if any(str(c)[:8] in self.cpv_codes or str(c) in self.cpv_codes for c in (a.cpv or [])):
            pts += self.w.get("cpv", 3)
            tags.append("cpv-71")

        bonus = self._count(title + " " + opis, self.kw.get("bonus", []))
        pts += self.w.get("bonus", 1) * bonus
        if bonus:
            tags.append("bonus-ue/strategiczny")

        cb, ctags = self._company_bonus(a.zamawiajacy)
        pts += cb
        tags.extend(ctags)

        # Kary — drogi (bez wyjątku) i infrastruktura (z wyjątkiem).
        # Kary mnożone przez wagę pola jak trafienia twarde: dopiero to
        # skutecznie NEUTRALIZUJE „prace projektowe w zakresie dróg/sieci"
        # (inaczej +3 w tytule zawsze przełamałoby karę −3 i sektor wcale
        # nie byłby wykluczany).
        def _hits(text: str, phrases: list[str], respect_exception: bool = False) -> int:
            n = 0
            for p in phrases:
                for pos in self._find(text, p):
                    if respect_exception and self._exception_near(text, pos):
                        continue
                    n += 1
            return n

        wt, wo = self.w.get("title", 2), self.w.get("opis", 1)
        pen = abs(self.w.get("negative", 3))
        road_pts = pen * (wt * _hits(title, self.kw.get("negative_road", []))
                          + wo * _hits(opis, self.kw.get("negative_road", [])))
        infra_pts = pen * (wt * _hits(title, self.kw.get("negative_infra", []), True)
                           + wo * _hits(opis, self.kw.get("negative_infra", []), True))
        if road_pts:
            pts -= road_pts
            tags.append("drogi")
        if infra_pts:
            pts -= infra_pts
            tags.append("infrastruktura")

        # Samorząd — niski priorytet, bez usuwania
        who = (a.zamawiajacy or "").lower() + " " + title.lower()
        if self._count(who, self.kw.get("low_priority", [])):
            pts += self.w.get("low_priority", -1)
            tags.append("samorząd")

        a.score = pts
        if a.termin_skladania is None:
            tags.append("brak-terminu")
        if pts >= self.t_high:
            tags.append("wysoka-trafnosc")
        a.tagi = sorted(set(tags))
        return a

    def should_publish(self, a: Announcement) -> bool:
        return a.score >= self.t_publish
