# Plan implementacji v2: Agregator ogłoszeń przetargowych dla biura architektonicznego

**Status:** wersja poprawiona po weryfikacji technicznej — patrz [WERYFIKACJA_PLANU.md](WERYFIKACJA_PLANU.md) dla uzasadnienia zmian względem [PLAN.md](PLAN.md).

**Cel:** codzienne, automatyczne wyszukiwanie ogłoszeń o przetargach/konkursach na prace projektowe architektoniczne i dokumentację wielobranżową, z publikacją wyników na statycznej stronie www hostowanej na GitHub Pages (koszt zerowy).

**Założenie:** implementacja wykonywana przez tani i szybki model (glm-5.3-flash) — plan rozbity na małe, izolowane, łatwo testowalne moduły z jednoznacznymi instrukcjami. Względem v1 dodano: rozwiązanie konfliktu limitów czasowych z crawl-delay platformazakupowa.pl, aktualne (nie martwe) źródło BZP, realistyczny zakres BIP-ów w MVP oraz mechanizm wykrywania cichych awarii scraperów.

---

## 0. Zadania wstępne (przed pisaniem kodu)

Te zadania są tanie (research/lektura), ale ich pominięcie prowadzi do zgadywania przez model implementujący — dlatego są wydzielone jako krok 0, wykonywany raz, ręcznie lub przez agenta z dostępem do sieci:

1. **Przeczytać aktualny regulamin platformazakupowa.pl** (obowiązuje od 10.12.2025) w części dot. automatyzacji/API/reużycia danych. Ustalić, czy automatyczne pobieranie ogłoszeń w ogóle jest dozwolone, i na jakich warunkach (User-Agent, częstotliwość, kontakt).
2. **Sprawdzić dostęp do API BZP na e-Zamówienia** (`ezamowienia.gov.pl`) — czy odczyt ogłoszeń rzeczywiście nie wymaga subskrypcji/klucza, czy jednak trzeba założyć konto w Portalu Dostępowym (`Regulamin korzystania z API`, media.ezamowienia.gov.pl). Zapisać wynik w `docs/zrodla-decyzje.md`.
3. **Zweryfikować pełną listę kodów CPV** istotnych dla usług architektonicznych/projektowych (dział 71, w tym m.in. 71200000, 71220000, 71221000, 71222000, 71240000, 71300000, 71320000, 71400000 — potwierdzić w oficjalnym słowniku CPV, nie zgadywać). Zapisać finalną listę w `config/cpv.yaml`.
4. Wybrać 3-5 spółek SP na pilotaż BIP (poza PHN) — patrz sekcja 2.4.

Wyniki kroku 0 są wejściem do `config/sources.yaml` i `config/cpv.yaml` — implementator nie podejmuje tych decyzji samodzielnie.

---

## 1. Kryteria selekcji ogłoszeń

Bez zmian względem v1 (potwierdzone jako trafne):

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
- **WAŻNE wyjątek:** fraza „wraz z niezbędną infrastrukturą" / „niezbędna infrastruktura towarzysząca" NIE może wykluczać ogłoszenia.

**Zmiana v2:** reguła wyjątku działa na polu `tytul` z wyższą wagą niż na polu `opis` (patrz sekcja 3) — patrz uzasadnienie w weryfikacji, pkt 2.1.

---

## 2. Źródła informacji (zrewidowane priorytety)

| # | Źródło | Dostęp techniczny | Priorytet | Faza | Zmiana vs v1 |
|---|--------|------------------|-----------|------|--------------|
| 1 | **TED (ted.europa.eu)** — CPV 71xxxxxx wg `config/cpv.yaml`, kraj PL | Publiczne API, anonimowy dostęp (potwierdzone: `docs.ted.europa.eu/api`) | WYSOKI | MVP | bez zmian |
| 2 | **e-Zamówienia / BZP** (`ezamowienia.gov.pl`) — ogłoszenia krajowe (progi 130 000 zł–UE), obejmuje też spółki SP działające jako zamawiający publiczni, nie tylko samorządy | Publiczne API odczytu (`/mo-board/api/v1/notice`), część danych w OCDS | WYSOKI | **MVP (przeniesione z Fazy 2)** | **awans z Fazy 2; poprawiony URL (był: `bzp1.portal.gov.pl`)** |
| 3 | **BIP-y spółek skarbu państwa** — pilotaż: PHN (`bip.phnsa.pl`, sprawdzone: Drupal, `Crawl-delay: 10`, statyczne HTML) + 3-4 kolejne spółki do wyboru w kroku 0.4 | Scraping per-spółka; **brak założenia wspólnego szablonu** — każda spółka to osobny plik parsera | WYSOKI (ograniczony zakres) | MVP (pilotaż 4-5 spółek) → Faza 2 (skalowanie do 30-50) | **zakres MVP zmniejszony z "30-50 spółek" do pilotażu** |
| 4 | **Platforma Zakupowa** (platformazakupowa.pl, OpenNexus) | Scraping HTML strony `/all` (potwierdzone: statyczne HTML, wyszukiwarka po frazach, paginacja) — **ale `Crawl-delay: 900s`**, więc pobieranie rozłożone w czasie (patrz sekcja 4.2) | WYSOKI (ale osobna architektura pobierania) | MVP, osobny workflow | **niezmieniony priorytet, ale całkowicie zmieniony sposób pobierania** |
| 5 | **ESPI/GPW** (espi.pl, komunikaty spółek giełdowych) | RSS/HTML | ŚREDNI | Faza 2 | bez zmian |
| 6 | **Konkursy architektoniczne** — SARP (sarp.org.pl), konkursy.org | RSS/scraping | NISKI | Faza 2 | bez zmian |
| 7 | **funduszeeuropejskie.gov.pl** — lista projektów z dofinansowaniem UE | Scraping listy | NISKI (informacyjnie) | Faza 3 | bez zmian |

**Zakres MVP (zmieniony):** źródła 1, 2, 3 (pilotaż), 4 (z osobną architekturą pobierania). Źródło 3 skaluje się do pełnej listy spółek dopiero w Fazie 2, po potwierdzeniu, że pilotaż działa stabilnie.

---

## 3. Filtrowanie — silnik scoringowy (deterministyczny, bez LLM w runtime)

Zasada z v1 potwierdzona jako trafny wybór (tanie, przewidywalne, testowalne), z jedną zmianą strukturalną:

- **Model `Announcement` rozdziela pola `tytul` i `opis`** (jeśli źródło dostarcza pełny opis) — scoring liczy trafienia osobno na obu polach, z wagą tytułu wyższą (np. ×2) niż opisu. To rozwiązuje niejednoznaczność reguły wyjątku „wraz z niezbędną infrastrukturą" (patrz weryfikacja 2.1): fraza wykluczająca w samym tytule waży więcej niż w dalszym opisie przedmiotu zamówienia.
- **Trafienia twarde (score +3):** „dokumentacja wielobranżowa", „prace projektowe w zakresie", „dokumentacja projektowa", „projektowanie architektoniczne"; „konkurs architektoniczny" (+2); CPV wg `config/cpv.yaml`
- **Bonus (+1):** zamawiający ze spółek SP/giełdowych (lista w YAML), frazy „dofinansowanie", „POIiS", „FEnIKS", „KPO", sektory strategiczne
- **Kary (−3):** frazy drogowo-infrastrukturalne (z wyjątkiem „wraz z niezbędną infrastrukturą" — patrz wyżej, ważone per pole)
- **Niski priorytet (−1, bez usunięcia):** zamawiający samorządowy (gmina/powiat/urząd)
- **Progi:** `score >= 3` → publikacja; `score >= 5` → tag „wysoka trafność"

Konfiguracja: wyłącznie w `config/keywords.yaml` i `config/cpv.yaml`.

**Nowość v2 — kalibracja progów:** po 1-2 tygodniach zbierania danych, ręczny przegląd wyników i korekta progów/wag na podstawie rzeczywistych trafień/pominięć (nie tylko jednorazowa kalibracja na starcie na `przykład_przetargu.eml`).

---

## 4. Architektura i publikacja

### 4.1 Struktura repo

```
scraper/
  sources/
    base.py               # interfejs: fetch(state) -> FetchResult(items, new_state)
    ted.py
    ezamowienia_bzp.py
    platformazakupowa.py  # tryb throttled — patrz 4.2
    bip/
      phn.py
      <spolka2>.py
      <spolka3>.py
      ...
  filters.py               # scoring wg keywords.yaml + cpv.yaml, ważenie tytul/opis
  dedup.py                 # hash URL+tytuł, historia 90 dni
  healthcheck.py           # sanity-check liczby wyników per źródło vs. średnia krocząca
  site.py                  # generator HTML (Jinja2)
config/
  sources.yaml             # lista BIP-ów spółek, spółek SP/giełdowych do scoringu
  keywords.yaml             # słowa kluczowe + progi + wagi tytul/opis
  cpv.yaml                  # zweryfikowane kody CPV (krok 0.3)
data/
  announcements.json        # wyniki publikowane (commitowane)
  pz_state.json              # stan throttlowanego pobierania z platformazakupowa.pl
  history/                   # rolling average do healthcheck (per źródło, per dzień)
  errors.log
docs/
  zrodla-decyzje.md          # wynik kroku 0 (ustalenia prawne/techniczne o źródłach)
templates/index.html.j2
.github/workflows/
  daily.yml                  # TED + BZP + BIP (pilotaż) + publish, raz dziennie
  platformazakupowa-poll.yml # throttled poll co ~20 min, patrz 4.2
```

- **Język:** Python 3.12; biblioteki: `httpx`, `selectolax` (lub BeautifulSoup4), `Jinja2`, `PyYAML`. (`feedparser` tylko jeśli po kroku 0 potwierdzi się realny kanał RSS — v1 zakładał RSS bez potwierdzenia jego istnienia.)
- **Model danych:** `Announcement` = data, zamawiający, tytul, opis (opcjonalnie), URL, score, tagi, źródło, cpv (opcjonalnie), hash
- **Strona www:** GitHub Pages — statyczna tabela (data, zamawiający, tytuł-link, score, tagi) + filtrowanie po tagach; UI po polsku

### 4.2 Pobieranie z platformazakupowa.pl — architektura throttled (zmiana kluczowa vs v1)

Ponieważ `robots.txt` serwisu wymaga `Crawl-delay: 900` (15 min), a pełne przejście listy (~129 stron) jednorazowo jest nierealne w oknie 10 minut GH Actions:

1. Osobny workflow `platformazakupowa-poll.yml`, harmonogram co ~20 minut (margines ponad wymagane 15 min).
2. Każde uruchomienie wykonuje **dokładnie jeden request** — jedno zapytanie z wyszukiwarki wg jednej frazy z rotowanej listy fraz w `keywords.yaml` (round-robin, stan rotacji w `data/pz_state.json`), tylko pierwsza strona wyników (lista jest sortowana od najnowszych — nowe trafienia pojawią się na górze, dedup obsłuży powtórki).
3. Wyniki dopisywane przyrostowo do `data/announcements.json` (z dedupem), commit po każdym pollu **tylko jeśli są nowe pozycje** (żeby nie zaśmiecać historii commitów).
4. Kod wymusza własny throttling (min. odstęp między requestami) niezależnie od harmonogramu cron — na wypadek ręcznego/dodatkowego uruchomienia.
5. Honest User-Agent z adresem kontaktowym (np. `arch-oglo-bot/1.0 (+kontakt: matkowpa@gmail.com)`), zgodnie z dobrą praktyką dla botów odwiedzających publiczne strony rządowe/przetargowe.

`daily.yml` osobno generuje stronę raz dziennie na podstawie tego, co zebrało się w `announcements.json` do tego momentu (z TED, BZP, BIP i tego, co poll zdążył zebrać) — strona nie czeka na "pełny" scrape platformazakupowa.pl, bo taki nie istnieje w tym modelu.

### 4.3 Healthcheck / wykrywanie cichych awarii

- Po każdym uruchomieniu `daily.yml`, `healthcheck.py` porównuje liczbę nowych wyników per źródło z 7-dniową średnią kroczącą (zapisaną w `data/history/`).
- Spadek >80% względem średniej (lub 0 wyników przy niezerowej średniej) → log `::warning::` widoczny w podsumowaniu GitHub Actions + wpis w `data/errors.log`.
- Nie blokuje publikacji — tylko ostrzega, żeby zmiana struktury strony źródłowej nie została niezauważona tygodniami.

### 4.4 Harmonogram

- `daily.yml`: `cron: '7 5 * * *'` (nieokrągła minuta — GitHub Actions kolejkuje pełne godziny/połówki z większym opóźnieniem; **nie jest to gwarancja dokładnej godziny**, typowe opóźnienia 5-30 min, w rzadkich przypadkach więcej — to świadomie zaakceptowane ograniczenie, opisane w README).
- `platformazakupowa-poll.yml`: `cron: '*/20 * * * *'`.
- Awaria jednego źródła nie przerywa runu (retry max 2, log błędów per źródło, try/except).

---

## 5. Zasady dla implementatora (glm-5.3-flash)

1. Każde źródło = osobny moduł z identycznym interfejsem `fetch(state) -> FetchResult`; do dodania nowego źródła wystarczy nowy plik + wpis w `sources.yaml`. **Nie zakładać wspólnej struktury HTML między różnymi BIP-ami spółek** — każdy plik w `sources/bip/` pisany i testowany osobno na zapisanej kopii danej strony.
2. Konfiguracja (słowa kluczowe, kody CPV, lista spółek, progi, wagi) tylko w YAML.
3. Testy na fixture: `przykład_przetargu.eml` (OpenNexus/platformazakupowa) i zapisana kopia strony `bip.phnsa.pl/ogloszenia/2`; dla każdego nowego źródła BIP w Fazie 2 — analogiczna zapisana kopia HTML jako fixture przed napisaniem parsera.
4. Scraping odporny: timeout, retry (max 2), log błędów do `data/errors.log`; jedno nieudane źródło (lub jedna nieudana spółka BIP) nie blokuje pozostałych.
5. **Throttling platformazakupowa.pl wymuszony w kodzie** (nie tylko przez harmonogram cron), honest User-Agent z kontaktem.
6. Commity i logi po angielsku; treść strony po polsku.
7. Bez LLM w runtime — czysty Python + regex/słowa kluczowe.
8. Limity GitHub Actions: `daily.yml` ≤ 10 min; `platformazakupowa-poll.yml` — pojedynczy request, ≤ 1 min; generowanie strony < 1 s.
9. Przed napisaniem adaptera do nowego źródła zewnętrznego (BIP, RSS) — sprawdzić `robots.txt` tego źródła i uwzględnić jego `Crawl-delay`, jeśli występuje (jak w przypadku platformazakupowa.pl — nie zakładać domyślnie `Crawl-delay: 10` jak u PHN).

---

## 6. Kroki implementacji (kolejność zadań)

0. **(Wstępne, patrz sekcja 0)** Lektura regulaminu platformazakupowa.pl, weryfikacja dostępu do API e-Zamówienia, finalna lista CPV, wybór spółek pilotażowych BIP.
1. Inicjalizacja repo: struktura, `requirements.txt`, `config/keywords.yaml`, `config/cpv.yaml`, `config/sources.yaml`, model `Announcement` (z `tytul`/`opis`)
2. Moduł `filters.py` + testy jednostkowe na przykładzie EML i PHN (w tym test na regułę wyjątku „niezbędna infrastruktura" ważoną per pole)
3. Adapter: TED API (CPV wg `config/cpv.yaml`, kraj PL)
4. Adapter: e-Zamówienia / BZP API
5. Adapter: BIP PHN + 3-4 kolejne spółki pilotażowe (osobne pliki, osobne fixtures)
6. Adapter: platformazakupowa.pl w trybie throttled (round-robin fraz, `data/pz_state.json`, wymuszony throttling w kodzie)
7. Dedup + zapis `data/announcements.json`
8. `healthcheck.py` — rolling average, ostrzeżenia o cichych awariach
9. Generator strony (Jinja2): tabela, tagi, sortowanie po score/dacie
10. Workflow `daily.yml` (cron na nieokrągłą minutę + Pages deploy) i `platformazakupowa-poll.yml`
11. README: instrukcja dodawania źródeł/spółek BIP, słów kluczowych, opis ograniczeń harmonogramu (patrz 4.4)
12. **Faza 2:** skalowanie BIP do 30-50 spółek, ESPI/GPW, SARP/konkursy.org
13. **Faza 3:** funduszeeuropejskie.gov.pl

---

## 7. Referencje (przykłady użytkownika)

- Ogłoszenie na BIP spółki SP: https://bip.phnsa.pl/ogloszenia/2
- Powiadomienie e-mail z platformy zakupowej: `przykład_przetargu.eml` (nadawca OZONE Architekci, generowane przez OpenNexus/platformazakupowa.pl)

## 8. Otwarte pytania (przeniesione z weryfikacji, wciąż wymagają decyzji)

1. Wybór 3-5 spółek SP na pilotaż BIP (poza PHN) — do ustalenia w kroku 0.4.
2. Czy po lekturze regulaminu platformazakupowa.pl (krok 0.1) throttled-polling opisany w 4.2 jest wystarczający, czy trzeba dodatkowo skontaktować się z OpenNexus o oficjalny dostęp.
