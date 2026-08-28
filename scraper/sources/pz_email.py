"""Źródło 1: platformazakupowa.pl przez Gmail IMAP (sekcja 4 final_plan.md).

UWAGA (4.2 — blokada sekwencyjna): parser działa na szablonie powiadomień
o NOWYCH postępowaniach. Przed wdrożeniem produkcyjnym trzeba zebrać 2–3 realne
maile jako fixtures (tests/fixtures/pz_*.eml) i dopasować wzorce poniżej.
`przykład_przetargu.eml` w repo to inny szablon (powiadomienie o wiadomości na
forum trwającego postępowania) — służy testowi scoringu tytułu, nie temu parserowi.

Odczyt: nieprzeczytane od nadawcy platformy -> parsowanie -> oznaczenie \\Seen.
Nie usuwać wiadomości (archiwum do debugowania). Sekrety tylko z env.
"""
from __future__ import annotations

import html
import imaplib
import os
import re
from email import policy
from email.parser import BytesParser

from ..model import Announcement
from .base import BaseSource

TRANSACTION_RE = re.compile(r"platformazakupowa\.pl/(?:transakcja|aukcja)/(\d+)", re.I)


class PzEmailSource(BaseSource):
    name = "platformazakupowa-email"

    def __init__(self, cfg: dict):
        self.enabled = bool(cfg.get("enabled", False))
        self.host = cfg.get("host", "imap.gmail.com")
        self.port = int(cfg.get("port", 993))
        self.user = os.environ.get(cfg.get("user_env", "GMAIL_USER"), "")
        self.password = os.environ.get(cfg.get("password_env", "GMAIL_APP_PASSWORD"), "")
        self.mailbox = cfg.get("mailbox", "INBOX")
        self.sender_contains = cfg.get("sender_contains", "platformazakupowa.pl")
        self.max_messages = int(cfg.get("max_messages", 50))

    def fetch(self) -> list[Announcement]:
        if not self.enabled:
            raise RuntimeError("pz_email disabled: platform has no CPV subscription "
                               "(see sources.yaml); kept dormant for other platforms")
        if not self.user or not self.password:
            raise RuntimeError("GMAIL_USER / GMAIL_APP_PASSWORD not set (secrets via env only)")
        imap = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            imap.login(self.user, self.password)
            imap.select(self.mailbox, readonly=False)
            status, data = imap.search(None, "UNSEEN")
            if status != "OK":
                return []
            out: list[Announcement] = []
            for num in data[0].split()[: self.max_messages]:
                st, msg_data = imap.fetch(num, "(RFC822)")
                if st != "OK" or not msg_data or msg_data[0] is None:
                    continue
                msg = BytesParser(policy=policy.default).parsebytes(msg_data[0][1])
                ann = self.parse_message(msg)
                if ann:
                    out.append(ann)
                imap.store(num, "+FLAGS", "\\Seen")
            return out
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def parse_message(self, msg) -> Announcement | None:
        sender = (msg.get("From") or "")
        if self.sender_contains.lower() not in sender.lower():
            return None
        subject = str(msg.get("Subject") or "").strip()
        body = self._body_text(msg)
        m = TRANSACTION_RE.search(body or "")
        url = f"https://platformazakupowa.pl/transakcja/{m.group(1)}" if m else ""
        if not subject or not url:
            return None  # bez URL/i tytułu nie budujemy ogłoszenia
        zamawiajacy = self._field(body, r"Zamawiaj[ąa]c[yi]:?\s*(.+)") or ""
        termin = self._field(body, r"(?:Termin|Do)\s+(?:składania|skladania)[^:]*:?\s*([\d.,:\-\/ ]+)")
        return Announcement(
            zrodlo=self.name,
            tytul=subject,
            url=url,
            zamawiajacy=zamawiajacy.strip()[:200],
            termin_skladania=termin.strip() if termin else None,
            opis=None,
            status_opisu="brak",
        )

    @staticmethod
    def _body_text(msg) -> str:
        part = msg.get_body(preferencelist=("plain",)) if msg.is_multipart() else msg
        if part is None:
            part = msg.get_body(preferencelist=("html",))
        if part is None:
            return ""
        text = part.get_content()
        if part.get_content_type() == "text/html":
            text = re.sub(r"<[^>]+>", " ", text)
        return html.unescape(text)

    @staticmethod
    def _field(body: str, pattern: str) -> str | None:
        m = re.search(pattern, body or "", re.I)
        return m.group(1).strip() if m else None
