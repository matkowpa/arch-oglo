"""Źródło 6: KGHM Polska Miedź S.A. — kghm.com (sekcja 7 final_plan.md).

Odkrycie 2026-08-29 (docs/zrodla-decyzje.md): zgłoszone w planie URL-e
(`/pl/przetargi`, `/pl/korporacyjne/przetargi`) są 404; właściwy spis to
`https://kghm.com/pl/przetargi-nieograniczone` (Drupal views, server-side,
10 wierszy/stronę, paginacja `?page=0..N`). robots.txt: brak dyrektyw
dla ścieżki (sonda 2026-08-29).
Parser pisany WYŁĄCZNIE przeciw fixture: tests/fixtures/kghm_przetargi.html.

Struktura: <table class="views-table cols-5"> — kolumny: Data publikacji,
Termin składania ofert, Kategoria, Tytuł (link do ogłoszenia), Data
aktualizacji; daty jako <time datetime="ISO">.

2026-11-06: dodane sekcje poboczne (`sections` w config/sources.yaml):
„Pozostałe ogłoszenia" i „Umowy ramowe otwarte". Ta sama tabela Drupala, ale
bez kolumny terminu, a data publikacji jest tekstem `YYYY-MM-DD` — parser czyta
oba warianty. Sekcja „Zakupy" to strona marketingowa bez tabeli, a właściwe
zapytania ofertowe siedzą na `oferty.kghm.com` (Mercus/SAP, formularz
`ajaxLogin/login`, brak publicznej listy — sonda 2026-11-06).
"""
from __future__ import annotations

import time
from urllib.parse import urljoin

import httpx
from selectolax.lexbor import LexborHTMLParser

from ...model import Announcement
from ..base import BaseSource


class KghmSource(BaseSource):
    name = "bip:kghm"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.list_url = cfg["list_url"]
        self.crawl_delay = int(cfg.get("crawl_delay", 10))
        self.pages = int(cfg.get("pages", 1))
        # Sekcje poboczne: [{url, pages}] — ten sam parser, inne kolumny
        self.sections = cfg.get("sections") or []
        self.timeout = timeout

    def _targets(self) -> list[tuple[str, int]]:
        out = [(self.list_url, self.pages)]
        for sec in self.sections:
            if isinstance(sec, str):
                out.append((sec, 1))
            elif isinstance(sec, dict) and sec.get("url"):
                out.append((sec["url"], int(sec.get("pages", 1))))
        return out

    def fetch(self) -> list[Announcement]:
        headers = {"User-Agent": "arch-oglo-aggregator/1.0 (contact: see repo)"}
        out: list[Announcement] = []
        first = True
        for base, pages in self._targets():
            for page in range(1, pages + 1):
                if not first:
                    time.sleep(self.crawl_delay)
                first = False
                url = self._page_url_for(base, page)
                r = httpx.get(url, headers=headers, timeout=self.timeout,
                              follow_redirects=True)
                r.raise_for_status()
                out.extend(self.parse(r.text, base_url=url))
        return out

    def _page_url(self, page: int) -> str:
        """Paginacja Drupal views, 0-based: strona 1 = list_url, dalej ?page=N."""
        return self._page_url_for(self.list_url, page)

    @staticmethod
    def _page_url_for(base: str, page: int) -> str:
        if page <= 1:
            return base
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}page={page - 1}"

    def parse(self, html: str, base_url: str = "") -> list[Announcement]:
        tree = LexborHTMLParser(html)
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
            if pub is not None and pub.attributes.get("datetime"):
                data = pub.attributes["datetime"][:10]
            else:
                # sekcje poboczne: data publikacji jako tekst YYYY-MM-DD
                cell = row.css_first("td.views-field-field-publishing-date")
                text = " ".join(cell.text().split()) if cell is not None else ""
                data = text[:10] if len(text) >= 10 and text[4] == "-" else None
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
