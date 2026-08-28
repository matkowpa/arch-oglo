"""Źródło 1 (nowe): publiczna wyszukiwarka platformazakupowa.pl — sito frazowe.

URL (krok 0.5, potwierdzony 2026-08-28): https://platformazakupowa.pl/all?page=1&limit=30&query=<fraza>
Dostęp anonimowy, wyniki HTML. robots.txt: Crawl-delay 900 -> architektura
zakłada MAKSYMALNIE 1 żądanie na frazę na run, a frazy są rozłożone na osobne
godziny w osobnych workflow (patrz .github/workflows/pz_search.yml).

Każdy wiersz wyniku: div.auction-row z a.auction-title (href /transakcja/{id}),
zamawiający jako tekst wiersza, termin w span.auction-time b (DD-MM-YYYY HH:MM:SS).
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote_plus, urljoin

import httpx
from selectolax.parser import HTMLParser

from ..model import Announcement
from .base import BaseSource

DATE_RE = re.compile(r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}")
ID_SUFFIX_RE = re.compile(r"\s*\(ID \d+\)\s*$")


class PzSearchSource(BaseSource):
    name = "pz-search"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.base_url = cfg.get("base_url", "https://platformazakupowa.pl/all").split("?")[0]
        self.phrases: list[str] = cfg.get("phrases", [])
        self.limit = int(cfg.get("limit", 30))
        self.timeout = timeout
        self._phrase = None  # fraza wybrana na dany run (ustawiana z zewnątrz lub wg dnia)

    def for_run(self, phrase: str | None = None) -> "PzSearchSource":
        """Wybiera frazę na ten run: jawnie podaną lub rotującą wg dnia miesiąca."""
        if phrase:
            self._phrase = phrase
        elif self.phrases:
            self._phrase = self.phrases[datetime.now().day % len(self.phrases)]
        return self

    def fetch(self) -> list[Announcement]:
        if not self._phrase:
            self.for_run()
        if not self._phrase:
            return []
        params = {"page": 1, "limit": self.limit, "query": self._phrase}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; arch-oglo-aggregator/1.0)"}
        r = httpx.get(self.base_url, params=params, headers=headers,
                      timeout=self.timeout, follow_redirects=True)
        r.raise_for_status()
        return self.parse(r.text)

    def parse(self, html: str) -> list[Announcement]:
        tree = HTMLParser(html)
        out: list[Announcement] = []
        for row in tree.css("div.auction-row"):
            a = row.css_first("a.auction-title")
            if a is None:
                continue
            tytul = " ".join((a.text() or "").split())
            raw_title = tytul  # wiersz zawiera tytuł z sufiksem (ID ...) — podmieniamy surowy
            tytul = ID_SUFFIX_RE.sub("", tytul).strip()
            href = (a.attributes or {}).get("href", "")
            if not tytul or not href:
                continue
            url = urljoin(self.base_url, href)

            tnode = row.css_first("span.auction-time b")
            termin = None
            if tnode is not None:
                m = DATE_RE.search(tnode.text() or "")
                if m:
                    termin = datetime.strptime(m.group(0), "%d-%m-%Y %H:%M:%S").isoformat(
                        sep=" ")

            # zamawiający: tekst wiersza bez tytułu, daty i etykiety
            row_text = " ".join((row.text() or "").split())
            remainder = row_text.replace(raw_title, "", 1)
            remainder = DATE_RE.sub("", remainder)
            remainder = re.sub(r"Postępowanie trwające:?", "", remainder)
            zamawiajacy = remainder.strip(" |·—–-")[:200]

            out.append(Announcement(
                zrodlo=self.name,
                tytul=tytul,
                url=url,
                zamawiajacy=zamawiajacy,
                termin_skladania=termin,
                status_opisu="brak",
            ))
        return out
