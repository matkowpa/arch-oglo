"""Źródło 2: TED API v3 (sekcja 5 final_plan.md). Potwierdzone kontrakty — nie zmieniać.

POST https://api.ted.europa.eu/v3/notices/search — dostęp anonimowy bez klucza.
Składnia strict: zaczynamy od prostego zapytania CPV; dodawać filtry po jednym.
Limity dostępu anonimowego nieudokumentowane -> backoff + obsługa HTTP 429.
"""
from __future__ import annotations

import httpx

from ..model import Announcement
from .base import BaseSource

FIELDS = ["publication-number", "notice-title", "buyer-name", "deadline", "classification-cpv"]


class TedSource(BaseSource):
    name = "ted"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.cfg = cfg
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        from datetime import datetime

        query = " ".join(self.cfg["query"].split())
        if self.cfg.get("only_open"):
            # dynamiczna data dzisiejsza — TED zwróci tylko otwarte terminy
            query += f" AND deadline>{datetime.now():%Y%m%d}"
        body = {
            "query": query,
            "fields": FIELDS,
            "limit": min(int(self.cfg.get("limit", 100)), 100),
            "scope": self.cfg.get("scope", "ACTIVE"),
            "paginationMode": "ITERATION",
            "page": 1,
        }
        for attempt in (1, 2):
            try:
                r = httpx.post(self.cfg["url"], json=body, timeout=self.timeout)
                if r.status_code == 429:  # backoff
                    import time

                    time.sleep(3 * attempt)
                    continue
                r.raise_for_status()
                return self._parse(r.json())
            except Exception:
                if attempt == 2:
                    raise
        return []

    def _parse(self, data: dict) -> list[Announcement]:
        out: list[Announcement] = []
        for n in (data.get("notices") or []):
            cpv = n.get("classification-cpv") or []
            if isinstance(cpv, str):
                cpv = [cpv]
            pub = n.get("publication-number") or ""
            out.append(
                Announcement(
                    zrodlo=self.name,
                    tytul=self._lang(n.get("notice-title")) or f"TED {pub}",
                    url=f"https://ted.europa.eu/en/notice/-/detail/{pub}",
                    zamawiajacy=self._lang(n.get("buyer-name")),
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
