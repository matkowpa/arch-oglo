"""Źródło: PSE — Platforma Zakupowa eB2B (przetargi.pse.pl).

Research 2026-09-03 (docs/zrodla-decyzje.md): publiczna lista postępowań
otwartych (/open-auctions.html, tytuł „Lista postępowań otwartych") ładuje
dane XHR-em GET {api_url}?start&limit — JSON {success, total, data};
dostęp anonimowy (wystarczy sesja PHPSESSID ze strony listy), POST -> 403.
Szczegóły postępowania są za loginem (wszystkie warianty URL -> 403), więc
url = strona listy (jak w parserze TAURON; unikalność zapewnia dedup wtórny
po zrodlo+tytul+zamawiajacy). robots.txt przetargi.pse.pl: 404 (brak dyrektyw).
Paginacja: total ~159, limit=100 OK, start działa (sonda: 100+59, brak
nakładania). Parser pisany przeciw fixture: tests/fixtures/pse_open_auctions.json.
"""
from __future__ import annotations

import time

import httpx

from ...model import Announcement
from ..base import BaseSource

HEADERS = {"User-Agent": "arch-oglo-aggregator/1.0 (contact: see repo)"}


class PseSource(BaseSource):
    name = "bip:pse"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.list_url = cfg["list_url"]           # strona listy (sesja PHPSESSID)
        self.api_url = cfg["api_url"]             # endpoint JSON (store ExtJS)
        self.limit = int(cfg.get("limit", 100))   # PageSize (sonda: 100 OK)
        self.max_requests = int(cfg.get("max_requests", 3))
        self.crawl_delay = int(cfg.get("crawl_delay", 10))
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        client = httpx.Client(headers=HEADERS, timeout=self.timeout,
                              follow_redirects=True)
        # sesja (PHPSESSID) przed endpointem — tak inicjuje ją strona listy
        r0 = client.get(self.list_url)
        r0.raise_for_status()
        out: list[Announcement] = []
        start = 0
        budget = self.max_requests
        while budget > 0:
            budget -= 1
            if start:
                time.sleep(self.crawl_delay)
            r = client.get(self.api_url, params={"start": start, "limit": self.limit})
            r.raise_for_status()
            data = r.json()
            rows = data.get("data") or []
            out.extend(self.parse(data))
            start += len(rows)
            total = int(data.get("total") or 0)
            if len(rows) < self.limit or start >= total:
                break  # ostatnia strona
        return out

    def parse(self, data: dict) -> list[Announcement]:
        out: list[Announcement] = []
        for row in (data or {}).get("data") or []:
            if row.get("is_test"):
                continue  # postępowania testowe platformy
            tytul = " ".join((row.get("name") or "").split())
            if not tytul:
                continue
            pub = (row.get("publication_date") or "")[:10] or None
            # termin składania ofert; w etapie RFI/wniosków bywa brak -> None
            termin = (row.get("offers_attachments_deadline_date")
                      or row.get("stage_offers_end_date") or None)
            out.append(
                Announcement(
                    zrodlo=self.name,
                    tytul=tytul,
                    url=self.list_url,  # szczegóły za loginem — url = strona listy
                    zamawiajacy=(row.get("company_name") or "").strip()
                    or "Polskie Sieci Elektroenergetyczne S.A.",
                    data_publikacji=pub,
                    termin_skladania=termin,
                    status_opisu="brak",
                )
            )
        return out
