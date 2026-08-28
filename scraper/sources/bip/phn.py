"""Źródło 4: BIP — Polski Holding Nieruchomości S.A. (sekcja 7 final_plan.md).

Parser pisany WYŁĄCZNIE przeciw fixture: tests/fixtures/phn_ogloszenia.html
(zapisana kopia https://bip.phnsa.pl/ogloszenia). robots.txt: Crawl-delay: 10.
Struktura: Drupal — lista ogłoszeń jako artykuły z linkiem „Czytaj więcej".
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from ...model import Announcement
from ..base import BaseSource

MONTHS_PL = {
    "sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6,
    "lip": 7, "sie": 8, "wrz": 9, "paź": 10, "lis": 11, "gru": 12,
}


class PhnSource(BaseSource):
    name = "bip:phn"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.list_url = cfg["list_url"]
        self.crawl_delay = int(cfg.get("crawl_delay", 10))
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        headers = {"User-Agent": "arch-oglo-aggregator/1.0 (contact: see repo)"}
        r = httpx.get(self.list_url, headers=headers, timeout=self.timeout, follow_redirects=True)
        r.raise_for_status()
        return self.parse(r.text, base_url=self.list_url)

    def parse(self, html: str, base_url: str = "") -> list[Announcement]:
        tree = HTMLParser(html)
        out: list[Announcement] = []
        # Struktura Drupal views: div.views-row z views-field-title / date-display-single
        for row in tree.css("div.views-row"):
            title_node = row.css_first("div.views-field-title .field-content, .views-field-title span")
            if title_node is None or not (title_node.text() or "").strip():
                continue
            tytul = title_node.text().strip()
            a_more = row.css_first('a')  # „Czytaj więcej" -> pełne ogłoszenie
            url = ""
            if a_more is not None and a_more.attributes.get("href"):
                url = urljoin(base_url, a_more.attributes["href"])
            date_node = row.css_first("span.date-display-single")
            data = None
            if date_node is not None and date_node.attributes.get("content"):
                data = date_node.attributes["content"][:10]
            out.append(
                Announcement(
                    zrodlo=self.name,
                    tytul=tytul,
                    url=url or base_url,
                    zamawiajacy="Polski Holding Nieruchomości S.A.",
                    data_publikacji=data,
                    status_opisu="brak",
                )
            )
        return out

    @staticmethod
    def _parse_date(text: str) -> str | None:
        # format na liście PHN: „21 kwi" / „19 mar" (rok = bieżący)
        m = re.search(r"\b(\d{1,2})\s+([a-ząćęłńóśźż]{3})\b", text or "")
        if not m:
            return None
        day, mon = int(m.group(1)), MONTHS_PL.get(m.group(2)[:3])
        if not mon:
            return None
        return datetime(datetime.now().year, mon, day).date().isoformat()
