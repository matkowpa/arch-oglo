"""Źródło: Polska Grupa Górnicza — przetargi zakupowe (pgg.pl).

Endpoint POTWIERDZONY sondą 2026-09-03 (docs/zrodla-decyzje.md): lista jest
renderowana do HTML-a przez POST `{ścieżka}-list` z tokenem CSRF, a nie przez
JS-owe API — dlatego `<main>` strony z listą jest pusty.

Sonda 2026-11-06 (50 wierszy na jednym żądaniu): kolumny to numer postępowania,
temat, komórka organizacyjna, podstawa prawna („objęty ustawą o ZP”),
kategoria (usługi/dostawy), data publikacji, termin składania ofert
(DD.MM.YYYY) i link do szczegółów obsługiwany JS-em (`href="ogloszenie"` +
`data-lp`), więc `url` = strona listy, a unikalność wpisu trzyma numer
postępowania w tytule.

Parser pisany WYŁĄCZNIE przeciw fixture: tests/fixtures/pgg_list.html.
"""
from __future__ import annotations

import re
import time

import httpx
from selectolax.lexbor import LexborHTMLParser

from ..model import Announcement
from .base import BaseSource

DATE_RE = re.compile(r"^\s*(\d{2})\.(\d{2})\.(\d{4})\s*$")
TOKEN_RES = (
    re.compile(r'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)"'),
    re.compile(r'<input[^>]+name="_token"[^>]+value="([^"]+)"'),
)


def _iso_date(value: str) -> str | None:
    """DD.MM.YYYY -> YYYY-MM-DD (PGG podaje daty bez czasu)."""
    m = DATE_RE.match(value or "")
    if not m:
        return None
    day, month, year = m.groups()
    return f"{year}-{month}-{day}"


class PggSource(BaseSource):
    name = "pgg"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.list_url = cfg["list_url"]
        self.crawl_delay = int(cfg.get("crawl_delay", 10))
        self.timeout = timeout

    @staticmethod
    def _token(html: str) -> str | None:
        for rx in TOKEN_RES:
            m = rx.search(html)
            if m:
                return m.group(1)
        return None

    def fetch(self) -> list[Announcement]:
        headers = {"User-Agent": "arch-oglo-aggregator/1.0 (contact: see repo)"}
        with httpx.Client(headers=headers, timeout=self.timeout,
                          follow_redirects=True) as client:
            page = client.get(self.list_url)
            page.raise_for_status()
            token = self._token(page.text)
            if not token:
                # Bez tokenu POST zwróci 419/403 — lepiej zgłosić błąd źródła niż
                # zapisać pustą listę i wyglądać na źródło bez ogłoszeń.
                raise RuntimeError("PGG: brak tokenu CSRF na stronie listy")
            time.sleep(self.crawl_delay)
            resp = client.post(
                self.list_url + "-list",
                data={"_token": token},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            resp.raise_for_status()
        return self.parse(resp.text, base_url=self.list_url)

    def parse(self, html: str, base_url: str = "") -> list[Announcement]:
        tree = LexborHTMLParser(html)
        table = tree.css_first("table")
        if table is None:
            return []
        out: list[Announcement] = []
        for row in table.css("tbody tr"):
            cells = row.css("td")
            if len(cells) < 7:
                continue
            text = [" ".join(c.text().split()) for c in cells]
            tytul = text[1]
            if not tytul:
                continue
            nr = text[0]
            komorka = text[2]
            zamawiajacy = "Polska Grupa Górnicza S.A."
            if komorka:
                zamawiajacy = f"{zamawiajacy} — {komorka}"
            out.append(
                Announcement(
                    zrodlo=self.name,
                    tytul=f"{nr} {tytul}".strip() if nr else tytul,
                    url=base_url,
                    zamawiajacy=zamawiajacy[:250],
                    data_publikacji=_iso_date(text[5]),
                    termin_skladania=_iso_date(text[6]),
                    status_opisu="brak",
                )
            )
        return out
