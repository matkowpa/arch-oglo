"""Źródło 6: KGHM Polska Miedź S.A. — kghm.com (sekcja 7 final_plan.md).

Odkrycie 2026-08-29 (docs/zrodla-decyzje.md): zgłoszone w planie URL-e
(`/pl/przetargi`, `/pl/korporacyjne/przetargi`) są 404; właściwy spis to
`https://kghm.com/pl/przetargi-nieograniczone` (Drupal views, server-side,
10 wierszy/stronę, paginacja `?page=0..N`). robots.txt: brak dyrektyw
dla ścieżki (sonda 2026-08-29).
Parser pisany WYŁĄCZNIE przeciw fixture: tests/fixtures/kghm_przetargi.html.

Struktura: <table class="views-table cols-5"> — kolumny: Data publikacji,
Termin składania ofert, Kategoria, Tytuł (link do ogłoszenia), Data
aktualizacji; daty jako <time datetime="ISO">. Pozostałe sekcje
(Pozostałe ogłoszenia, Umowy ramowe, Zapytania ofertowe) — do rozszerzenia
w późniejszych iteracjach, jeśli okażą się potrzebne.
"""
from __future__ import annotations

import time
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from ...model import Announcement
from ..base import BaseSource
class KghmSource(BaseSource):
    name = "bip:kghm"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.list_url = cfg["list_url"]
        self.crawl_delay = int(cfg.get("crawl_delay", 10))
        self.pages = int(cfg.get("pages", 1))
        self.timeout = timeout

    def _page_url(self, page: int) -> str:
        """Paginacja Drupal views, 0-based: strona 1 = list_url, dalej ?page=N."""
        if page <= 1:
            return self.list_url
        sep = "&" if "?" in self.list_url else "?"
        return f"{self.list_url}{sep}page={page - 1}"

    def fetch(self) -> list[Announcement]:
        headers = {"User-Agent": "arch-oglo-aggregator/1.0 (contact: see repo)"}
        out: list[Announcement] = []
        for page in range(1, self.pages + 1):
            if page > 1:
                time.sleep(self.crawl_delay)
            r = httpx.get(self._page_url(page), headers=headers, timeout=self.timeout,
                          follow_redirects=True)
            r.raise_for_status()
            out.extend(self.parse(r.text, base_url=self._page_url(page)))
        return out

    def parse(self, html: str, base_url: str = "") -> list[Announcement]:
        tree = HTMLParser(html)
        table = tree.css_first("table.views-table")
        if table is None:
            return []
        out: list[Announcement] = []
        for row in table.css("tbody tr"):
            title_a = row.css_first("td.views-field-title a")
            if title_a is None or not (title_a.text() or "").strip():
                continue
            tytul = title_a.text().strip()
            url = ""
            if title_a.attributes.get("href"):
                url = urljoin(base_url, title_a.attributes["href"])
            pub = row.css_first("td.views-field-field-start-date time")
            data = (pub.attributes.get("datetime") or "")[:10] or None if pub else None
            end = row.css_first("td.views-field-field-response-deadline time")
            termin = (end.attributes.get("datetime") or None) if end else None
            out.append(
                Announcement(
                    zrodlo=self.name,
                    tytul=tytul,
                    url=url or base_url,
                    zamawiajacy="KGHM Polska Miedź S.A.",
                    data_publikacji=data,
                    termin_skladania=termin,
                    status_opisu="brak",
                )
            )
        return out
