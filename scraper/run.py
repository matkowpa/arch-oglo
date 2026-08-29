"""Orkiestrator dziennego runu (sekcja 8.2): źródła -> scoring -> dedup -> healthcheck -> strona.

Izolacja awarii: try/except per źródło — jedno nieudane nie przerywa runu.
"""
from __future__ import annotations

import logging
import os
import sys

import yaml

from .envtools import load_dotenv
from .dedup import load_existing, merge, save
from .filters import Scorer
from .healthcheck import check, record_run
from .model import Announcement
from .site import render_site
from .sources.bzp import BzpSource
from .sources.bip.kghm import KghmSource
from .sources.bip.phn import PhnSource
from .sources.bip.tauron import TauronSource
from .sources.pz_email import PzEmailSource
from .sources.pz_search import PzSearchSource
from .sources.ted import TedSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
DATA = os.path.join(ROOT, "data")
ANNOUNCEMENTS = os.path.join(DATA, "announcements.json")
HISTORY = os.path.join(DATA, "history")
LOG = os.path.join(DATA, "errors.log")
SITE_OUT = os.path.join(ROOT, "docs_site")

log = logging.getLogger("arch-oglo")


def load_yaml(name: str) -> dict:
    with open(os.path.join(CONFIG, name), encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_sources() -> list:
    s = load_yaml("sources.yaml")
    cpv_codes = [str(c) for c in load_yaml("cpv.yaml").get("cpv", [])]
    out = [TedSource(s["ted"])]
    # BIP-y spółek: rejestr id -> parser (sekcja 7; nowe spółki = nowy parser + wpis)
    bip_parsers = {"phn": PhnSource, "tauron": TauronSource, "kghm": KghmSource}
    for company in s.get("bip", {}).get("companies", []):
        cls = bip_parsers.get(company.get("id"))
        if cls is not None and company.get("enabled", True):
            out.append(cls(company))
    pz_email = PzEmailSource(s["email"])
    if pz_email.enabled:
        out.append(pz_email)
    pz_search = PzSearchSource(s["platformazakupowa_search"]).for_run(
        os.environ.get("PZ_PHRASE") or None  # fraza z workflow pz_search.yml
    )
    if pz_search._phrase:
        out.append(pz_search)
    bzp = BzpSource(s["bzp"], cpv_codes=cpv_codes)
    if bzp.enabled:
        out.append(bzp)
    return out


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    keywords, cpv, weights, sources_cfg = (
        load_yaml("keywords.yaml"),
        load_yaml("cpv.yaml"),
        load_yaml("weights.yaml"),
        load_yaml("sources.yaml"),
    )
    scorer = Scorer(keywords, cpv, weights, sources_cfg)

    per_source: dict[str, dict] = {}
    incoming: list[Announcement] = []
    for src in build_sources():
        try:
            items = src.fetch()
            per_source[src.name] = {"ok": True, "count": len(items)}
            incoming.extend(items)
        except Exception as e:  # izolacja awarii
            per_source[src.name] = {"ok": False, "count": 0}
            log.error("source %s failed: %s", src.name, e)
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(f"{src.name}: {e}\n")

    scored = [scorer.score(a) for a in incoming]
    scored = [a for a in scored if scorer.should_publish(a)]

    merged = merge(load_existing(ANNOUNCEMENTS), scored,
                   history_days=int(sources_cfg.get("history_days", 90)),
                   prune_undated=("ted",) if sources_cfg.get("ted", {}).get("only_open") else ())
    save(ANNOUNCEMENTS, merged)

    record_run(HISTORY, per_source)
    for line in check(HISTORY, per_source):
        print(line, file=sys.stderr)  # GitHub Actions ::error::/::warning::

    failed = [name for name, st in per_source.items() if not st.get("ok")]
    render_site(ANNOUNCEMENTS, SITE_OUT, display_days=int(sources_cfg.get("display_days", 30)),
                failed_sources=failed)
    log.info("done: %d published, %d total in store", len(scored), len(merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
