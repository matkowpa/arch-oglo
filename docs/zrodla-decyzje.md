# Rozstrzygnięcia źródeł — wyniki kroku 0 (final_plan.md, sekcje 6 i 9)

## Krok 0.2 — BZP / e-Zamówienia: ROZSTRZYGNIĘTY (2026-08-29)

Badanie empiryczne (sondy HTTP, anonimowo, bez rejestracji). Potwierdzony endpoint:

```
GET https://ezamowienia.gov.pl/mo-board/api/v1/notice
```

### Odpowiedzi na pytania z sekcji 6 planu

1. **Który adres odpowiada i w jakim formacie?**
   - `https://ezamowienia.gov.pl/mo-board/api/v1/notice` → **działa**, `application/json` (tablica ogłoszeń).
     Bez wymaganych parametrów zwraca HTTP 400 z listą brakujących pól (HttpResponseException
     w formacie RFC 7231 — co potwierdza, że endpoint istnieje i jest dokumentowany przez własne błędy).
   - `https://ezamowienia.gov.pl/mo-client-board/api/notices/` → HTTP 200, ale to **SPA (HTML)**, nie API.
2. **Czy odczyt wymaga klucza/rejestracji?** — **NIE.** Dostęp w pełni anonimowy (User-Agent własny).
3. **Filtrowanie po CPV/dacie?**
   - **Data: TAK** (obowiązkowe): `PublicationDateFrom` / `PublicationDateTo` (ISO date, zakres włącznie).
   - **CPV: NIE.** Parametr `CpvCodes` jest **ignorowany** przez API (sonda: identyczne wyniki z nim i bez niego).
     Konsekwencja: pobieramy ogłoszenia z okna publikacji i **filtrujemy lokalnie** wg `config/cpv.yaml`.
   - Obowiązkowe parametry: `NoticeType` (jedyna potwierdzona wartość: **`ContractNotice`**),
     `PublicationDateFrom`, `PublicationDateTo`, `PageSize` (≤100), `PageNumber`.
4. **Dzienny wolumen:** ~300–500 ogłoszeń dziennie (cała Polska). Przy `PageSize=100` run dzienny
   to **kilkanaście żądań** (paginacja do pustej strony / `max_pages`).
5. **Regulamin / limity:** `robots.txt` domeny jest **pusty** (2 bajty, brak dyrektyw). Odczyt GET
   REST nie jest zabroniony; nie stwierdzono limitów. Mimo to: timeout + izolacja awarii per źródło
   (sekcja 8.3 planu) stosowane jak wszędzie.

### Pola rekordu używane przez adapter

| Pole API | Znaczenie | Pole modelu |
|---|---|---|
| `orderObject` | przedmiot zamówienia | `tytul` |
| `cpvCode` | kody CPV z opisami, przecinkami (`71220000-6 (…),…`) | `cpv` (regex `\d{8}-\d+`) |
| `submittingOffersDate` | **termin składania ofert** (ISO UTC) | `termin_skladania` |
| `organizationName` | zamawiający | `zamawiajacy` |
| `publicationDate` | data publikacji | `data_publikacji` |
| `htmlBody` | pełne ogłoszenie HTML | `opis` (strip tagów, ≤2000 znaków), `status_opisu='pobrany'` |

**URL publiczny ogłoszenia:** link kanoniczny w `htmlBody`:
`https://ezamowienia.gov.pl/mp-client/search/list/{tenderId}` (sonda: HTTP 200). Fallback: konstrukcja z `tenderId`.

### Rozstrzygnięcie paginacji (sondy 2026-08-29 — po wdrożeniu v1)

- **Paginacja NIE ISTNIEJE:** parametry `PageNumber`, `Page`, `PageIndex`, `Skip` są **ignorowane**
  (sonda: strony 1 i 2 identyczne). API zwraca najnowsze `PageSize` wyników okna (max 100).
- **Daty przyjmują pełne ISO datetime** (`2026-08-28T06:00:00Z`) — sprawdzono 4 okna po 6 h
  (każde pełne: 100 wyników → wolumen ~400+/dzień).
- **Wdrożone rozwiązanie:** adaptacyjne dzielenie okna czasowego na pół przy trafieniu
  w limit (`max_depth: 3`, budżet `max_requests: 20`), duplikaty na granicach okien usuwa
  dedup po hash. Logika przetestowana offline w `tests/test_bzp.py`.

### Wdrożenie


- Adapter: `scraper/sources/bzp.py` (`BzpSource`), fixture: `tests/fixtures/bzp_notices.json`
  (2 rekordy z CPV 71*, 1 bez — test filtra lokalnego), testy: `tests/test_bzp.py`.
- Konfiguracja: `config/sources.yaml` → sekcja `bzp` (`enabled: true`, `notice_type`,
  `page_size: 100`, `max_pages: 8`, `days_back: 1`).
- Filtr lokalny: co najmniej jeden kod CPV ogłoszenia ∈ `config/cpv.yaml`.

---

## Pilotaż BIP — spółki 2–5 (KGHM, PGE, PGG, ARP): sondy 2026-08-29

Zgodnie z sekcją 7 planu — przed parserem weryfikacja dostępności statycznego HTML + robots.txt.
**Wynik: żadna z 4 spółek nie udostępnia dziś prostego, statycznego spisu ogłoszeń — parsery
odłożone** (zasada 10.9: zgłosić, nie improwizować):

| Spółka | Sonda | Wniosek |
|---|---|---|
| KGHM | `kghm.com/pl/przetargi` i `/pl/korporacyjne/przetargi` → **404** (robots.txt: 2 KB, do przejrzenia) | Właściwy URL spisu wymaga researchu w serwisie kghm.com; do dokończenia w kroku 0 |
| PGE | `gkpge.pl/...` → wszystko zwraca **371-bajtową powłokę HTML** (ochrona anty-bot / SPA) | Statyczny scraping niemożliwy; plan przewiduje PGE głównie przez **Logintrade** (kanał IMAP, Faza 2) |
| PGG | `pgg.pl/przetargi` → HTTP 200, ale **treść renderowana w JS** (brak listy w DOM, robots.txt pusty) | Wymaga przeglądarki/headless albo odnalezienia API klienta — poza MVP |
| ARP | `arp.com.pl` → **ConnectTimeout** (niedostępne z tego środowiska) | Sprawdzić ponownie z innego IP (runner GH Actions) lub znaleźć BIP ARP |

**Rekomendacja:** luka pokrycia spółek SP jest częściowo zapełniona przez BZP (ogłoszenia
powyżej progu PZP) i TED. Spółki prowadzące postępowania **poza reżimem PZP** pozostają
domknięte dopiero w Fazie 2 (Logintrade/IMAP) albo po odnalezieniu statycznych spisów.

---

## Rozszerzenie BIP: research spółek 2–8 (2026-08-29, Faza 0 planu rozszerzenia)

Sondy read-only GET (User-Agent własny). Wstępnie z tej maszyny; **sondy rozstrzygające
powtarzać z runnera** (`.github/workflows/bip_probe.yml`), bo lokalny DNS/sieć zwraca
ConnectError/timeout dla części domen (jsw.com.pl, kontrakty.orlen.pl, grupa.enea.pl,
biuletyny.tauron.pl, arp.com.pl).

### TAURON — WDROŻONE (źródło 5)

- **Kluczowe odkrycie:** statyczna strona `www.tauron.pl/tauron/przetargi` (server-side,
  roboty budowlane tabelka) zawiera **wyłącznie archiwalny wpis z 2017 r.** — jest martwa
  dla naszego celu. Realne ogłoszenia całej grupy (~10 spółek) publikuje **SWOZ**:
  `https://swoz.tauron.pl/platform/demand/notice/public/current/list`.
- **SWOZ = platforma Mercus** (`mp_gridTable`, `data-mpgrid-id`) — tej samej rodziny co
  sekcja „Mercus" w menu KGHM; wskazówka, że parser może się przydać dla kolejnych spółek.
- **Potwierdzone empirycznie:** HTTP 200, HTML renderowany serwerowo (25–30 wierszy/stronę,
  wpisy z 2026 r.), robots.txt: **brak** (404 → brak zakazów), bez rejestracji.
- Struktura: `<table id="publicList">`, nagłówek to zwykły `<tr><th>` (bez `<thead>`),
  kolumny: number, name, procedureType, realizationType, type, categoryItem,
  publicationDate, stageEndDate, responsiblePerson, namePurchaser. Wiersz **nie zawiera
  linku do szczegółów** (nawigacja JS) → `url` = strona listy; unikalność po tytule.
- Paginacja formularzowa (POST `searchform`) — dla MVP strona 1 (30 najnowszych);
  wolumen dzienny grupy TAURON jest od niej znacznie niższy.
- Parser: `scraper/sources/bip/tauron.py`, fixture `tests/fixtures/tauron_swoz_list.html`.

### Pozostałe spółki — stan po sondach lokalnych

| Spółka | Sonda | Wniosek |
|---|---|---|
| PGG | `pgg.pl/przetargi` → hub **server-side**; podstrona „Przed terminem składania ofert" 200, 49 KB | **Kandydat Tier A** — parser po ustaleniu dokładnych URL-i podstron |
| KGHM | menu kghm.com ma sekcje (Przetargi nieograniczone, Pozostałe ogłoszenia, Umowy ramowe, Zapytania ofertowe, Mercus); zgłoszone URL-e → 404 | Kandydat Tier A po odkryciu właściwych URL-i (sonda z runnera + linki z homepage) |
| PKP Intercity | stopka → „Dla dostawców i wykonawców" + BIP; zgłoszony URL → 404 | Profil idealny (dworce); ustalić miejsce publikacji sondą z runnera |
| Enea | `www.enea.pl/przetargi` → 404; `grupa.enea.pl` — DNS nieosiągalny lokalnie | Sonda z runnera zdecyduje |
| ARP | timeout lokalnie | Sonda z runnera |
| PSE | `pse.pl/przetargi` → tylko link do platformy `przetargi.pse.pl` | Tier B: research API platformy (jak BZP) |
| PGE | Logintrade / `strefazakupow.pge.pl` | Faza 2 (kanał IMAP / research API) |

---

## Rezerwa — niesprawdzone

- Pozostałe wartości `NoticeType` (400 dla: `DirectContractNotice`, `ContractAwardNotice`,
  `PlanningNotice`, `ChangeContractNotice`, `SimpleContractNotice`). Jeżeli kiedyś potrzebne
  ogłoszenia o udzieleniu zamówienia — sondować inne nazwy enuma.
- `mo-board/api/v1/notice` dla dłuższych okien publikacji: paginacja sprawdzona do 500 rekordów
  (2 dni); przy większych oknach łączyć strony aż do odpowiedzi < `PageSize`.
