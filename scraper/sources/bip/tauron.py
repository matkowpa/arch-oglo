"""Źródło 5: SWOZ — Platforma Zakupowa Grupy TAURON (swoz.tauron.pl).

Odkrycie 2026-08-29 (docs/zrodla-decyzje.md): statyczna strona
www.tauron.pl/tauron/przetargi zawiera tylko archiwalny wpis z 2017 r.;
aktualne ogłoszenia całej grupy publikuje SWOZ (platforma Mercus,
server-side HTML, ~30 wierszy/stronę, robots.txt: brak — 404).
Parser pisany WYŁĄCZNIE przeciw fixture: tests/fixtures/tauron_swoz_list.html
(zapisana kopia .../platform/demand/notice/public/current/list).

Struktura: <table id="publicList" class="mp_gridTable"> — kolumny opisane
atrybutami data-mpgrid-id (number, name, ..., publicationDate, stageEndDate,
namePurchaser). Paginacja formularzowa (POST) — dla MVP pobieramy stronę 1
(30 najnowszych); wolumen dzienny grupy TAURON jest od niej znacznie niższy.
"""
from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from ...model import Announcement
from ..base import BaseSource


class TauronSource(BaseSource):
    name = "bip:tauron"

    def __init__(self, cfg: dict, timeout: float = 30.0):
        self.list_url = cfg["list_url"]
        self.crawl_delay = int(cfg.get("crawl_delay", 10))
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        headers = {"User-Agent": "arch-oglo-aggregator/1.0 (contact: see repo)"}
        r = httpx.get(self.list_url, headers=headers, timeout=self.timeout,
                      follow_redirects=True)
        r.raise_for_status()
        return self.parse(r.text, base_url=self.list_url)

    def parse(self, html: str, base_url: str = "") -> list[Announcement]:
        tree = HTMLParser(html)
        table = tree.css_first("table#publicList")
        if table is None:
            return []
        # Mapa kolumna-index -> data-mpgrid-id (odporne na zmianę kolejności);
        # UWAGA: tabela nie ma <thead> — nagłówek to zwykły <tr><th>
        ids = [th.attributes.get("data-mpgrid-id")
               for th in table.css("th[data-mpgrid-id]")]
        out: list[Announcement] = []
        for row in table.css("tr.dataRow"):
            cells = dict(zip(ids, row.css("td")))
            name_cell = cells.get("name")
            if name_cell is None or not (name_cell.text() or "").strip():
                continue
            tytul = name_cell.text().strip()
            zamawiajacy = (cells.get("namePurchaser").text().strip()
                           if cells.get("namePurchaser") else "")
            pub = cells.get("publicationDate")
            data = (pub.text().strip() or None) if pub else None
            end = cells.get("stageEndDate")
            termin = (end.text().strip() or None) if end else None
            # Brak linku do szczegółów w wierszu (nawigacja JS) — url = strona listy
            out.append(
                Announcement(
                    zrodlo=self.name,
                    tytul=tytul,
                    url=base_url or self.list_url,
                    zamawiajacy=zamawiajacy,
                    data_publikacji=data,
                    termin_skladania=termin,
                    status_opisu="brak",
                )
            )
        return out
