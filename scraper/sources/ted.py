"""Źródło 2: TED API v3 (sekcja 5 final_plan.md). Potwierdzone kontrakty — nie zmieniać.

POST https://api.ted.europa.eu/v3/notices/search — dostęp anonimowy bez klucza.
Składnia strict: zaczynamy od prostego zapytania CPV; dodawać filtry po jednym.
Limity dostępu anonimowego nieudokumentowane -> backoff + obsługa HTTP 429.
"""
from __future__ import annotations

import httpx

from ..model import Announcement
from .base import BaseSource

FIELDS = ["publication-number", "notice-title", "buyer-name", "deadline",
          "classification-cpv", "publication-date"]


class TedSource(BaseSource):
    name = "ted"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.cfg = cfg
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        import time
        from datetime import datetime

        query = " ".join(self.cfg["query"].split())
        if self.cfg.get("only_open"):
            # UWAGA (2026-08-30): TED indeksuje termin złożenia ofert w DWÓCH
            # polach, zależnie od formatu ogłoszenia:
            #  - `deadline` — ogłoszenia eForms (publikowane bezpośrednio w TED),
            #  - `deadline-receipt-request` — legacy UBL (konwersje z platform
            #    krajowych, np. polskiego BZP). Pola są ROZŁĄCZNE: zapytanie
            #    tylko po `deadline` gubi większość polskich ogłoszeń (sonda:
            #    8 vs 438 dla 9 kodów CPV + POL). Stąd OR obu pól.
            today = datetime.now().strftime("%Y%m%d")
            query += f" AND (deadline>{today} OR deadline-receipt-request>{today})"
        limit = min(int(self.cfg.get("limit", 100)), 100)
        pages = int(self.cfg.get("pages", 1))
        out: list[Announcement] = []
        for page in range(1, pages + 1):
            body = {
                "query": query,
                "fields": FIELDS,
                "limit": limit,
                "scope": self.cfg.get("scope", "ACTIVE"),
                "paginationMode": "ITERATION",
                "page": page,
            }
            notices = None
            for attempt in (1, 2):
                try:
                    r = httpx.post(self.cfg["url"], json=body, timeout=self.timeout)
                    if r.status_code == 429:  # backoff
                        time.sleep(3 * attempt)
                        continue
                    r.raise_for_status()
                    notices = r.json().get("notices") or []
                    break
                except Exception:
                    if attempt == 2:
                        raise
            if notices is None:
                break  # obie próby nieudane — izolacja: reszta runu działa dalej
            out.extend(self._parse({"notices": notices}))
            if len(notices) < limit:
                break  # ostatnia strona
            if page < pages:
                time.sleep(self.cfg.get("crawl_delay", 5))  # fair-use między stronami
        return out

    def _parse(self, data: dict) -> list[Announcement]:
        out: list[Announcement] = []
        for n in (data.get("notices") or []):
            cpv = n.get("classification-cpv") or []
            if isinstance(cpv, str):
                cpv = [cpv]
            pub = n.get("publication-number") or ""
            pub_date = n.get("publication-date")
            # data publikacji — kluczowa dla legacy UBL (brak `deadline`):
            # bez niej merge/strona nie mają z czego policzyć świeżości
            data = (self._lang(pub_date) or "")[:10] or None
            out.append(
                Announcement(
                    zrodlo=self.name,
                    tytul=self._lang(n.get("notice-title")) or f"TED {pub}",
                    url=f"https://ted.europa.eu/en/notice/-/detail/{pub}",
                    zamawiajacy=self._lang(n.get("buyer-name")),
                    data_publikacji=data,
                    termin_skladania=self._lang(n.get("deadline")) or None,
                    cpv=cpv,
                    status_opisu="brak",
                )
            )
        return out

    def _lang(self, value) -> str:
        """Pola TED są wielojęzyczne: str | dict[lang, list[str]] | list — preferuj pol, potem eng."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for lang in ("pol", "eng"):
                v = value.get(lang)
                if v:
                    return self._lang(v)
            for v in value.values():
                if v:
                    return self._lang(v)
            return ""
        if isinstance(value, (list, tuple)):
            return self._lang(value[0]) if value else ""
        return str(value).strip()
