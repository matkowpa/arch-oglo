# Plan implementacji: Agregator ogłoszeń przetargowych dla biura architektonicznego

**Cel:** codzienne, automatyczne wyszukiwanie ogłoszeń o przetargach/konkursach na prace projektowe architektoniczne i dokumentację wielobranżową, z publikacją wyników na statycznej stronie www hostowanej na GitHub Pages (koszt zerowy).

**Założenie:** implementacja wykonywana przez tani i szybki model (glm-5.3-flash) — plan musi być rozbity na małe, izolowane, łatwo testowalne moduły z jednoznacznymi instrukcjami.

---

## 1. Kryteria selekcji ogłoszeń

### Interesują nas (priorytet wysoki)
- Przetargi na **prace projektowe architektury** lub **dokumentację wielobranżową**
- Frazy: „sporządzenie dokumentacji wielobranżowej", „prace projektowe w zakresie…", „dokumentacja projektowa"
- Zamawiający: **spółki skarbu państwa / z udziałem SP**
- Projekty z **dofinansowaniem unijnym** (POIiS, FEnIKS, KPO, RRF)
- Projekty w **sektorach strategicznych** (energetyka, obronność, kolej, ICT, przemysł)
- Przetargi/konkursy spółek **akcyjnych i giełdowych**

### Interesują nas (priorytet niższy)
- **Konkursy architektoniczne**
- Przetargi **samorządowe** (gminy, powiaty) — NIE usuwać, tylko niżej rankować

### Wykluczenia (ale ostrożnie)
- Prace projektowe w zakresie **dróg** (score −3)
- Prace projektowe w zakresie **infrastruktury/sieci** (kanalizacja, wodociągi, gaz, ciepłownictwo, elektroenergetyka dystrybucyjna) (score −3)
- **WAŻNE wyjątek:** fraza „wraz z niezbędną infrastrukturą" / „niezbędna infrastruktura towarzysząca" NIE może wykluczać ogłoszenia — wykluczenie działa tylko na frazy typu „drogowy", „sieć kanalizacyjna", „sieć wodociągowa" itp. w kontekście przedmiotu zamówienia.

---

## 2. Źródła informacji

| # | Źródło | Dostęp techniczny | Priorytet | Faza |
|---|--------|------------------|-----------|------|
| 1 | **Platforma Zakupowa** (platformazakupowa.pl, OpenNexus) — najczęstsze miejsce ogłoszeń spółek SP; przykładowy e-mail powiadomienia pochodzi stamtąd | RSS kanały ogłoszeń + scraping HTML list ogłoszeń | WYSOKI | MVP |
| 2 | **BIP-y spółek skarbu państwa** — lista spółek pod nadzorem MPiT; przykłady: `bip.phnsa.pl/ogloszenia` (Polski Holding Nieruchomości S.A. — statyczne HTML, łatwe parsowanie), PGE, KGHM, ARP, PGW, PFR itd. | Scraping stron „Ogłoszenia i przetargi" (statyczne HTML) — lista spółek w `config/sources.yaml`, łatwo rozszerzalna | WYSOKI | MVP |
| 3 | **TED (ted.europa.eu)** — ogłoszenia unijne, CPV 71200000-2 / 71300000-0 / 71400000-3, kraj PL | Publiczne API XML (stabilne, oficjalne) | ŚREDNI | MVP |
| 4 | **ESPI/GPW** (espi.pl, komunikaty spółek giełdowych) | RSS/HTML | ŚREDNI | Faza 2 |
| 5 | **BZP** (bzp1.portal.gov.pl) — głównie samorządy (niski priorytet wg wymagań); bywa odporna na boty | Wyszukiwarka web / ew. API; plan B: tylko filtrowanie z innych źródeł | NISKI | Faza 2 |
| 6 | **Konkursy architektoniczne** — SARP (sarp.org.pl), konkursy.org | RSS/scraping | NISKI | Faza 2 |
| 7 | **funduszeeuropejskie.gov.pl** — lista projektów z dofinansowaniem UE (kontekst: zapowiadane zamówienia na dokumentację) | Scraping listy | NISKI (informacyjnie) | Faza 3 |

**Zakres MVP:** źródła 1–3. Pozostałe w kolejnych fazach — architektura ma umożliwiać dodanie źródła przez jeden plik + wpis w YAML.

## 3. Filtrowanie — silnik scoringowy (deterministyczny, bez LLM w runtime)

Prosta reguła punktowa zamiast AI — tanie, szybkie, przewidywalne, łatwe do testowania:

- **Trafienia twarde (score +3):** „dokumentacja wielobranżowa", „prace projektowe w zakresie", „dokumentacja projektowa", „projektowanie architektoniczne"; „konkurs architektoniczny" (+2); CPV 712xxxxx / 713xxxxx
- **Bonus (+1):** zamawiający ze spółek SP/giełdowych (na podstawie listy w YAML), frazy „dofinansowanie", „POIiS", „FEnIKS", „KPO", sektory strategiczne („energetyka", „kolej", „obronność", „data center")
- **Kary (−3):** frazy drogowo-infrastrukturalne (z wyjątkiem „wraz z niezbędną infrastrukturą")
- **Niski priorytet (−1, bez usunięcia):** zamawiający samorządowy (gmina/powiat/urząd)
- **Progi:** `score >= 3` → publikacja; `score >= 5` → tag „wysoka trafność"

Konfiguracja słów kluczowych i progów: **wyłącznie w `config/keywords.yaml`** (nie w kodzie).

---

## 4. Architektura i publikacja

- **Język:** Python 3.12; biblioteki: `httpx`, `feedparser`, `selectolax` (lub BeautifulSoup4), `Jinja2`, `PyYAML`
- **Struktura repo:**
  ```
  scraper/
    sources/base.py        # interfejs: fetch() -> list[Announcement]
    sources/platformazakupowa.py
    sources/bip_spolki.py
    sources/ted.py
    filters.py             # scoring wg keywords.yaml
    dedup.py               # hash URL+tytuł, historia 90 dni
    site.py                # generator HTML (Jinja2)
  config/
    sources.yaml           # lista BIP-ów spółek itp.
    keywords.yaml          # słowa kluczowe + progi
  data/
    announcements.json     # wyniki (commitowane)
  templates/index.html.j2
  .github/workflows/daily.yml
  ```
- **Model danych:** `Announcement` = data, zamawiający, tytuł, URL, score, tagi, źródło, hash
- **Strona www:** GitHub Pages — statyczna tabela (data, zamawiający, tytuł-link, score, tagi) + filtrowanie po tagach; UI po polsku
- **Harmonogram:** GitHub Actions `cron: '0 5 * * *'` (raz dziennie, UTC) → scraper → jeśli zmiany: commit danych → Pages. Awaria jednego źródła nie przerywa runu (retry + log, try/except per źródło).

---

## 5. Zasady dla implementatora (glm-5.3-flash)

1. Każde źródło = osobny moduł z identycznym interfejsem `fetch() -> list[Announcement]`; do dodania nowego źródła wystarczy nowy plik + wpis w `sources.yaml`.
2. Konfiguracja (słowa kluczowe, lista spółek, progi) tylko w YAML.
3. Testy na fixture: `przykład_przetargu.eml` (OpenNexus/platformazakupowa) i zapisana kopia strony `bip.phnsa.pl/ogloszenia/2`.
4. Scraping odporny: timeout, retry (max 2), log błędów do `data/errors.log`; jedno nieudane źródło nie blokuje pozostałych.
5. Commity i logi po angielsku; treść strony po polsku.
6. Bez LLM w runtime — czysty Python + regex/słowa kluczowe.
7. Limity GitHub Actions: scrape ≤ 10 min; generowanie strony < 1 s.

---

## 6. Kroki implementacji (kolejność zadań)

1. Inicjalizacja repo: struktura, `requirements.txt`, `config/keywords.yaml`, `config/sources.yaml`, model `Announcement`
2. Moduł `filters.py` + testy jednostkowe na przykładzie EML i PHN
3. Adapter: Platforma Zakupowa (RSS + HTML)
4. Adapter: BIP-y spółek SP (lista startowa 30–50 spółek w YAML, rozszerzalna)
5. Adapter: TED API (CPV 71*, PL)
6. Dedup + zapis `data/announcements.json`
7. Generator strony (Jinja2): tabela, tagi, sortowanie po score/dacie
8. Workflow GitHub Actions (cron + Pages deploy)
9. README: instrukcja dodawania źródeł i słów kluczowych

---

## 7. Referencje (przykłady użytkownika)

- Ogłoszenie na BIP spółki SP: https://bip.phnsa.pl/ogloszenia/2
- Powiadomienie e-mail z platformy zakupowej: `przykład_przetargu.eml` (nadawca OZONE Architekci, generowane przez OpenNexus/platformazakupowa.pl)
