"""Test połączenia z Gmail IMAP — bezpieczna diagnoza źródła 1.

Nie pobiera treści maili — tylko: login, liczbę nieprzeczytanych, listę
nadawców/tematów (pierwszych 10) i ewentualne dopasowania do wzorca parsera.
Uruchomienie: python -m scraper.test_imap
"""
from __future__ import annotations

import imaplib
import sys

from .envtools import load_dotenv
from .sources.pz_email import PzEmailSource


def _load_email_cfg() -> dict:
    import os

    import yaml

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "config", "sources.yaml"), encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("email", {})


def main() -> int:
    load_dotenv()
    src = PzEmailSource(_load_email_cfg())
    if not src.user or not src.password:
        print("BŁĄD: .env nie zawiera GMAIL_USER / GMAIL_APP_PASSWORD (lub wartości są puste)")
        return 1

    print(f"Łączę się: {src.user} -> {src.host}:{src.port} ...")
    try:
        imap = imaplib.IMAP4_SSL(src.host, src.port)
        imap.login(src.user, src.password)
    except imaplib.IMAP4.error as e:
        print(f"BŁĄD LOGOWANIA: {e}")
        print("Typowe przyczyny: App Password skopiowany z literówką / 2SV nie włączone /")
        print("Google zablokowało logowanie IMAP (sprawdź https://mail.google.com -> ustawienia IMAP).")
        return 2
    print("LOGIN OK")

    imap.select(src.mailbox, readonly=True)
    status, data = imap.search(None, "UNSEEN")
    unread = data[0].split() if status == "OK" else []
    print(f"Nieprzeczytane: {len(unread)}")

    status, _all = imap.search(None, "ALL")
    total = len(_all[0].split()) if status == "OK" else 0
    print(f"Łącznie wiadomości w {src.mailbox}: {total}")

    # Podejrzenie tematów ostatnich 10 (bez treści)
    from email import policy
    from email.parser import BytesParser

    ids = (data[0].split() if False else []) or imap.search(None, "ALL")[1][0].split()[-10:]
    for num in reversed(ids):
        st, md = imap.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        if st != "OK" or not md or md[0] is None:
            continue
        msg = BytesParser(policy=policy.default).parsebytes(md[0][1])
        frm = str(msg.get("From", ""))[:50]
        subj = str(msg.get("Subject", ""))[:80]
        match = " [od platformy]" if src.sender_contains.lower() in frm.lower() else ""
        print(f"  #{num.decode()}: {frm}{match} :: {subj}")
    imap.logout()
    print("GOTOWE — jeśli powyżej widać maile od platformy, źródło 1 jest gotowe do testów parsera.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
