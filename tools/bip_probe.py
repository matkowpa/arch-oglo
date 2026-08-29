"""Faza 0: sonda dostępności stron przetargowych spółek SP — uruchamiać z runnera
GitHub Actions (workflow: .github/workflows/bip_probe.yml), bo lokalna sieć/DNS
zafałszowuje wyniki (2026-08-29: jsw, orlen, enea-grupa, biuletyny.tauron, arp).

Read-only GET. Wynik: log + podsumowanie w $GITHUB_STEP_SUMMARY (jeśli obecne).
Kryteria wejścia spółki do Tier A: status 200 + HTML server-side + robots.txt
nie zabrania ścieżki.
"""
from __future__ import annotations

import os
import re

import httpx

HEADERS = {"User-Agent": "arch-oglo-aggregator/1.0 (contact: see repo)"}

# (nazwa, URL) — kandydaci z researchu 2026-08-29 (docs/zrodla-decyzje.md)
CANDIDATES = [
    ("ARP", "https://www.arp.com.pl/"),
    ("ARP-przetargi", "https://www.arp.com.pl/przetargi"),
    ("Enea-grupa", "https://grupa.enea.pl/przetargi"),
    ("Enea-www", "https://www.enea.pl/"),
    ("JSW", "https://www.jsw.com.pl/"),
    ("JSW-przetargi", "https://www.jsw.com.pl/przetargi"),
    ("PSE-platforma", "https://przetargi.pse.pl/"),
    ("PGE-strefa", "https://strefazakupow.pge.pl/"),
    ("Orlen-kontrakty", "https://kontrakty.orlen.pl/"),
    ("Intercity-dostawcy", "https://www.intercity.pl/pl/site/dla-dostawcow-i-wykonawcow/"),
    ("Intercity-BIP", "https://bip.intercity.pl/"),
    ("KGHM-strona", "https://kghm.com/pl"),
    ("PGG-hub", "https://www.pgg.pl/przetargi"),
]


def _probe(client: httpx.Client, name: str, url: str) -> dict:
    rec: dict = {"name": name, "url": url}
    try:
        r = client.get(url, timeout=20, follow_redirects=True)
        rec["status"] = r.status_code
        rec["size"] = len(r.text)
        rec["final"] = str(r.url)
        t = r.text
        rec["spa"] = bool(re.search(r"__NEXT_DATA__|ng-app|react-root|vue-app", t, re.I))
        # linki do podstron przetargowych (odkrycie właściwych URL-i)
        links = sorted(set(re.findall(
            r'href=["\']([^"\']*(?:przetarg|zamowien|ogloszen|dostawc)[^"\']*)', t, re.I)))
        rec["links"] = links[:12]
    except Exception as e:
        rec["status"] = f"ERR {type(e).__name__}: {str(e)[:80]}"
    return rec


def main() -> None:
    lines = ["| nazwa | status | B | SPA | linki |", "|---|---|---|---|---|"]
    with httpx.Client(headers=HEADERS) as client:
        for name, url in CANDIDATES:
            rec = _probe(client, name, url)
            print(f"[{rec['name']}] {rec['status']} {rec.get('final', '')}")
            for l in rec.get("links", []):
                print(f"    link: {l[:120]}")
            status = str(rec.get("status", ""))
            lines.append(f"| {rec['name']} | {status} | {rec.get('size', '-')} "
                         f"| {rec.get('spa', '-')} | {len(rec.get('links', []))} |")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### Sonda BIP spółek (read-only)\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
