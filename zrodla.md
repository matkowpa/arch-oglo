# Źródła danych — logika wyszukiwania i pobierania

Dokument zbiorczy: jak każde źródło wyszukuje ogłoszenia, co decyduje o „zgodności z frazą", ile danych pobieramy i jakie są limity. Szczegóły decyzji badawczych: `docs/zrodla-decyzje.md`. Konfiguracja: `config/sources.yaml`.

**Wspólna zasada:** żadne źródło samo nie decyduje o publikacji. Każdy parser zwraca surowe ogłoszenia, które przechodzą przez wspólny pipeline: **scoring** (`scraper/filters.py` — frazy z `config/keywords.yaml`, kody CPV z `config/cpv.yaml`, bonusy za spółki SP/giełdowe, kary za drogi/kolej) → **próg publikacji** → **dedup** (`scraper/dedup.py` — po URL, wtórnie po tytule+zamawiającym+źródle) → magazyn `data/announcements.json` → strona.

---

## 1. pz-search — platformazakupowa.pl, wyszukiwarka `/all`

**Plik:** `scraper/sources/pz_search.py` · Workflow: `.github/workflows/pz_search.yml` (6 runów dziennie, 05–10:07 UTC)

- **Jak wyszukuje:** `GET https://platformazakupowa.pl/all?query=<fraza>&page=1&limit=30` — publiczna wyszukiwarka portalu, dostęp anonimowy.
- **Co znaczy „zgodne z frazą":** dopasowanie decyduje **platforma** (pełnotekstowe po jej stronie — tytuł/opis); nasz kod nie filtruje wyników po frazie, tylko przekazuje `query` i bierze co platforma zwróci. Frazy rotują: 6 fraz z `sources.yaml` (`platformazakupowa_search.phrases`), wybór wg godziny runu (`(godzina−5) mod 6`); frazę można też podać ręcznie w `workflow_dispatch`.
- **Zakres pobrania:** strona 1 wyników (~30 wierszy, `div.auction-row`): tytuł (bez sufixu „(ID …)"), zamawiający, termin składania (`span.auction-time`), link do transakcji.
- **Limity:** robots.txt platformy wymaga `Crawl-delay: 900 s` → **1 żądanie na run**, każda fraza w osobnej godzinie. Budżet: 6 × ~30 wierszy dziennie przed scoringiem.
- **Rola w systemie:** jedyne źródło postępowań **poza reżimem PZP** (spółki, fundacje — tego nie ma w BZP).

## 2. TED — api.ted.europa.eu (ogłoszenia unijne)

**Plik:** `scraper/sources/ted.py` · Uruchamiane w każdym runie (daily + pz-search)

- **Jak wyszukuje:** `POST https://api.ted.europa.eu/v3/notices/search` (API v3, anonimowe, bez klucza). Zapytanie strict: `classification-cpv IN (9 kodów 71*) AND buyer-country=POL` + dynamiczny filtr `deadline>dziś` (`only_open: true`) — dzięki niemu TED zwraca **tylko otwarte** postępowania i pole terminu jest wypełnione.
- **Co znaczy „zgodne":** tu filtrem są **kody CPV w zapytaniu** (nie frazy) — wyszukiwarka TED dopasowuje klasyfikację przedmiotu; dopasowanie decyduje silnik TED.
- **Zakres pobrania:** `limit: 100`, `scope: ACTIVE`, strona 1 (paginacja ITERATION — nie wykorzystywana).
- **Odporność:** backoff na HTTP 429 (2 próby); pola wielojęzyczne — preferuj `pol`, fallback `eng`.


## 3. BZP — ezamowienia.gov.pl (główne źródło krajowe, PZP > 130 tys. zł)

**Plik:** `scraper/sources/bzp.py` · Uruchamiane w każdym runie

- **Jak wyszukuje:** `GET https://ezamowienia.gov.pl/mo-board/api/v1/notice` — anonimowe REST API; `NoticeType=ContractNotice`, okno `PublicationDateFrom = teraz − 24 h` (`days_back: 1`).
- **Co znaczy „zgodne":** API **ignoruje filtr CPV** — pobieramy wszystkie ogłoszenia z doby (~300–500) i **filtrujemy lokalnie** po `config/cpv.yaml`. Dopasowanie fraz robi dopiero scoring.
- **Semantyka API (odkryta sondami, `docs/zrodla-decyzje.md`):** `PublicationDateTo` wymagane, ale **ignorowane**; **brak paginacji**; wyniki DESC; `PageSize ≤ 500`. Pokrycie całej doby przez **przewijanie `From`**: paczki po 500, przesuwanie `From` na najstarszą publikację w paczce → 1–3 żądania dziennie (budżet `max_requests: 6`).
- **Rola w systemie:** gwarancja ustawowa kompletności dla wszystkich zamówień publicznych PZP powyżej progu krajowego.

## 4. PHN — bip.phnsa.pl (BIP spółki SP)

**Plik:** `scraper/sources/bip/phn.py` · config: `bip.companies[id=phn]`

- **Jak wyszukuje:** brak wyszukiwarki — pobieramy **listę ogłoszeń**: `GET https://bip.phnsa.pl/ogloszenia/N`, strony **1–3** (`pages: 3`), przerwa `Crawl-delay: 10 s` między żądaniami.
- **Co znaczy „zgodne":** nic nie jest filtrowane przy pobraniu — bierzemy całą listę (Drupal views, `div.views-row`, link „Czytaj więcej"), selekcję robi scoring.
- **Limity:** robots.txt: `Crawl-delay: 10`.

## 5. TAURON — SWOZ (swoz.tauron.pl, platforma Mercus)

**Plik:** `scraper/sources/bip/tauron.py` · config: `bip.companies[id=tauron]`

- **Jak wyszukuje:** brak wyszukiwarki — `GET https://swoz.tauron.pl/platform/demand/notice/public/current/list` (**strona 1** — ~30 najnowszych ogłoszeń całej grupy TAURON; paginacja formularzowa POST, nie wykorzystywana w MVP).
- **Co znaczy „zgodne":** bez filtrów przy pobraniu — tabela `#publicList` (kolumny mapowane po `data-mpgrid-id`: nazwa, zamawiający, data publikacji, termin etapu); selekcję robi scoring.
- **Limity:** robots.txt: brak dyrektyw; `crawl_delay: 10` między ewentualnymi żądaniami. Wiersze nie mają linków (nawigacja JS) — url = strona listy.

## 6. KGHM — kghm.com/pl/przetargi-nieograniczone

**Plik:** `scraper/sources/bip/kghm.py` · config: `bip.companies[id=kghm]`

- **Jak wyszukuje:** brak wyszukiwarki — Drupal views: `GET /pl/przetargi-nieograniczone` + paginacja `?page=0..N`, **strony 1–2** (`pages: 2` → 2 × 10 najnowszych), przerwa 10 s.
- **Co znaczy „zgodne":** bez filtrów przy pobraniu — tabela `views-table` (tytuł z linkiem, daty z `<time datetime="ISO">`); selekcję robi scoring.
- **Możliwe rozszerzenie:** sekcje „Pozostałe ogłoszenia", „Umowy ramowe", „Zapytania ofertowe" — po obserwacji wolumenu.

---

## Źródła nieaktywne / zamknięte (dla pełności obrazu)

| Źródło | Status | Powód |
|---|---|---|
| **pz-email** (IMAP platformazakupowa.pl) | 🔌 dormant (`enabled: false`) | platforma nie oferuje subskrypcji CPV (potwierdzone 2026-08-28); kod gotowy na powiadomienia z innych platform (Faza 2) |
| **PGG** | ⏸ odłożone | listy renderowane w JS (pusty `<main>`, aplikacja Vite); powrót po znalezieniu endpointu JSON |
| **PSE** (`przetargi.pse.pl`) | 🕐 Faza 2 | platforma żywa (200); wymaga researchu API (analogia do BZP) |
| **PGE** | 🕐 Faza 2 | kanał = Logintrade; wymaga researchu |
| **ARP, Enea, JSW, Orlen, Intercity** | 🔒 zamknięte | sonda z runnera (`bip_probe.yml`): timeout / DNS nie istnieje / WAF 403 — brak dostępnego spisu ogłoszeń |

## Harmonogram i odświeżanie

- **daily-scrape** — cron 05:07 UTC (+ zapasowy slot 12:30 UTC) — pełny run wszystkich źródeł + deploy strony.
- **pz-search** — cron 6× dziennie (05–10:07 UTC), każda godzina = jedna fraza; **każdy run odświeża też pozostałe aktywne źródła** (pełny pipeline), więc magazyn i strona aktualizują się de facto do 7× dziennie.
- Każdy run: scoring → dedup → commit `data/` (heartbeat) → deploy na GitHub Pages (workflow `deploy-pages`).
