"""Źródło 3: BZP / e-Zamówienia (sekcja 6 final_plan.md).

STAN: NIEZWERYFIKOWANE. Dwa kandydujące endpointy; żaden nie został
potwierdzony empirycznie. Zgodnie z planem (krok 0.2): dopóty ten adapter
pozostaje wyłączony (sources.yaml: bzp.enabled: false) i fetch() zwraca pustą
listę, jednocześnie raportując status ok=False (healthcheck widzi lukę).
Po rozstrzygnięciu kroku 0.2 uzupełnić _parse() o realny format odpowiedzi.
"""
from __future__ import annotations

from ..model import Announcement
from .base import BaseSource


class BzpSource(BaseSource):
    name = "bzp"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.enabled = bool(cfg.get("enabled", False))

    def fetch(self) -> list[Announcement]:
        if not self.enabled:
            raise RuntimeError("bzp disabled pending step 0.2 (endpoint unverified)")
        # Po weryfikacji kroku 0.2: httpx.get(endpoint), filtrowanie po CPV/dacie,
        # parsowanie do Announcement. NIE improwizować — patrz zasada 9 sekcji 10.
        raise NotImplementedError("implement after docs/zrodla-decyzje.md step 0.2")
