"""Źródło 3: BZP / e-Zamówienia (sekcja 6 final_plan.md).

Krok 0.2 ROZSTRZYGNIĘTY empirycznie 2026-08-29 (szczegóły: docs/zrodla-decyzje.md):
- GET https://ezamowienia.gov.pl/mo-board/api/v1/notice — anonimowo, bez klucza.
- Wymagane parametry: NoticeType=ContractNotice (jedyna potwierdzona wartość),
  PublicationDateFrom/PublicationDateTo (ISO date, włącznie), PageNumber,
  PageSize (<=100).
- API NIE filtruje po CPV (parametr CpvCodes ignorowany) — pobieramy ogłoszenia
  krajowe z okna publikacji (~300–500/dzień) i filtrujemy LOKALNIE wg
  config/cpv.yaml.
- Pola: orderObject (tytuł), cpvCode ("kody+opisy", przecinkami),
  submittingOffersDate (termin składania, ISO UTC), organizationName,
  publicationDate, htmlBody (pełne ogłoszenie — opis po strip-tagach).
- Kanoniczny URL publiczny ogłoszenia: link w htmlBody
  https://ezamowienia.gov.pl/mp-client/search/list/{tenderId}.
- robots.txt domeny: pusty (brak ograniczeń); Regulamin API
  (media.ezamowienia.gov.pl) nie nakłada znanych limitów na odczyt.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx

from ..model import Announcement
from .base import BaseSource

CPV_RE = re.compile(r"\d{8}-\d+")
URL_RE = re.compile(r"https://ezamowienia\.gov\.pl/mp-client/search/list/[^\s\"'<>]+")
TAG_RE = re.compile(r"<[^>]+>")
HEADERS = {"User-Agent": "arch-oglo-aggregator/1.0 (contact: see repo)"}


class BzpSource(BaseSource):
    name = "bzp"

    def __init__(self, cfg: dict, cpv_codes: list[str] | None = None, timeout: float = 30.0):
        self.enabled = bool(cfg.get("enabled", False))
        self.url = cfg.get("url", "https://ezamowienia.gov.pl/mo-board/api/v1/notice")
        self.notice_type = cfg.get("notice_type", "ContractNotice")
        self.page_size = min(int(cfg.get("page_size", 500)), 500)
        self.days_back = int(cfg.get("days_back", 1))
        self.max_requests = int(cfg.get("max_requests", 6))
        self.cpv_codes = [str(c) for c in (cpv_codes or [])]
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        """Pełne pokrycie okna [now-days_back, now] metodą przewijania From.

        Semantyka API (sondy 2026-08-29, docs/zrodla-decyzje.md):
        - `PublicationDateTo` jest OBOWIĄZKOWE, ale jego WARTOŚĆ jest ignorowana
          (filtr działa wyłącznie od `PublicationDateFrom` w górę);
        - brak paginacji (parametry ignorowane), wyniki sortowane DESC po dacie
          publikacji, limit `PageSize <= 500`.
        Dlatego: pobieramy paczki (500) i przesuwamy `From` na najstarszą
        publikację w paczce, aż zejdziemy poniżej okna / dojdziemy do końca.
        Duplikaty między paczkami usuwa dedup po hash (i lokalnie po bzpNumber).
        """
        if not self.enabled:
            raise RuntimeError("bzp disabled (sources.yaml)")
        now = datetime.now(timezone.utc)
        from_ = now - timedelta(days=self.days_back)
        self._budget = self.max_requests
        out: list[Announcement] = []
        seen: set = set()
        while self._budget > 0:
            self._budget -= 1
            batch = self._get_page(from_, now)
            new = [n for n in batch if n.get("bzpNumber") not in seen]
            if not new:
                break
            seen.update(n.get("bzpNumber") for n in new if n.get("bzpNumber"))
            out.extend(self.parse(new))
            if len(batch) < self.page_size:
                break  # ostatnia paczka — pokryliśmy całe okno
            dates = sorted(n["publicationDate"] for n in new if n.get("publicationDate"))
            if not dates:
                break
            oldest = datetime.fromisoformat(dates[0].replace("Z", "+00:00"))
            if oldest <= from_:
                break
            from_ = oldest + timedelta(seconds=1)
        return out

    def _get_page(self, frm: datetime, to: datetime) -> list[dict]:
        params = {
            "PageSize": self.page_size,
            "NoticeType": self.notice_type,
            "PublicationDateFrom": frm.isoformat().replace("+00:00", "Z"),
            "PublicationDateTo": to.isoformat().replace("+00:00", "Z"),
        }
        r = httpx.get(self.url, params=params, headers=HEADERS, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def parse(self, notices: list[dict]) -> list[Announcement]:
        out: list[Announcement] = []
        for n in notices or []:
            cpv = CPV_RE.findall(n.get("cpvCode") or "")
            if self.cpv_codes and not (set(c.split("-")[0] for c in cpv) & set(self.cpv_codes)):
                continue  # brak CPV 71* — pomijamy (filtr lokalny, patrz docstring)
            tytul = " ".join((n.get("orderObject") or "").split())
            if not tytul:
                continue
            out.append(Announcement(
                zrodlo=self.name,
                tytul=tytul,
                url=self._url(n),
                zamawiajacy=(n.get("organizationName") or "").strip()[:200],
                data_publikacji=(n.get("publicationDate") or "")[:10] or None,
                termin_skladania=n.get("submittingOffersDate") or None,
                opis=self._opis(n.get("htmlBody") or ""),
                cpv=cpv,
                status_opisu="pobrany" if n.get("htmlBody") else "brak",
            ))
        return out

    @staticmethod
    def _url(n: dict) -> str:
        m = URL_RE.search(n.get("htmlBody") or "")
        if m:
            return m.group(0)
        return f"https://ezamowienia.gov.pl/mp-client/search/list/{n.get('tenderId', '')}"

    @staticmethod
    def _opis(html_body: str) -> str | None:
        if not html_body:
            return None
        text = " ".join(TAG_RE.sub(" ", html_body).split())
        return text[:2000]
