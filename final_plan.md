# Plan finalny: Agregator ogłoszeń przetargowych dla biura architektonicznego

**Status:** wersja obowiązująca. Ten plik (`final_plan.md`) jest kopią [plan_v3.md](plan_v3.md) (przechodzi do historii) i zastępuje [PLAN.md](PLAN.md) oraz [PLAN_V2.md](PLAN_V2.md). Uzasadnienie zmian: [WERYFIKACJA_PLANU.md](WERYFIKACJA_PLANU.md) i [WERYFIKACJA_PLANU_V2.md](WERYFIKACJA_PLANU_V2.md).

**Cel:** codzienne, automatyczne zbieranie ogłoszeń o przetargach/konkursach na prace projektowe architektoniczne i dokumentację wielobranżową, z publikacją na statycznej stronie www na GitHub Pages.

**Implementator:** tani i szybki model (glm-5.3-flash). Plan jest specyfikacją — moduły są małe, izolowane, z jednoznacznymi instrukcjami i konkretnymi endpointami. Model **nie podejmuje decyzji architektonicznych ani nie zgaduje adresów API** — jeśli czegoś brakuje, zgłasza to zamiast improwizować.

## Decyzje podjęte (nie podlegają zmianie przez implementatora)

| Decyzja | Wybór | Konsekwencja |
|---|---|---|
| Repozytorium | **publiczne** | GitHub Actions i Pages bez kosztów; **`config/keywords.yaml` i lista spółek są jawne** — świadomie zaakceptowane |
| Główne źródło z platformazakupowa.pl | **powiadomienia e-mail (IMAP), nie scraping** | brak problemu z `Crawl-delay: 900`, brak ryzyka regulaminowego, dane w modelu push |
| Skrzynka | **dedykowane konto Gmail** | darmowe, IMAP działa z App Password; Proton wykluczony (IMAP tylko w planie płatnym + Bridge to aplikacja desktopowa, nie działa w CI) |
| LLM w runtime | **nie** | scoring deterministyczny: Python + regex + YAML |

---

## 1. Kryteria selekcji ogłoszeń

### Interesują nas (priorytet wysoki)
- Przetargi na **prace projektowe architektury** lub **dokumentację wielobranżową**
- Frazy: „sporządzenie dokumentacji wielobranżowej", „prace projektowe w zakresie…", „dokumentacja projektowa", „dokumentacja projektowo-kosztorysowa"
- Zamawiający: **spółki skarbu państwa / z udziałem SP**
- Projekty z **dofinansowaniem unijnym** (POIiS, FEnIKS, KPO, RRF)
- Projekty w **sektorach strategicznych** (energetyka, obronność, kolej, ICT, przemysł)
- Przetargi/konkursy spółek **akcyjnych i giełdowych**

### Interesują nas (priorytet niższy)
- **Konkursy architektoniczne**
- Przetargi **samorządowe** (gminy, powiaty) — NIE usuwać, tylko niżej rankować

### Wykluczenia (ostrożne)
- Prace projektowe w zakresie **dróg** (−3)
- Prace projektowe w zakresie **infrastruktury/sieci** (kanalizacja, wodociągi, gaz, ciepłownictwo, elektroenergetyka dystrybucyjna) (−3)
- **Wyjątek bezwzględny:** frazy „wraz z niezbędną infrastrukturą", „niezbędna infrastruktura towarzysząca" **nie mogą** wykluczać ogłoszenia. Implementacja: dopasowanie tych fraz jest sprawdzane **przed** karami i blokuje karę infrastrukturalną dla danego wystąpienia.

---

## 2. Źródła — architektura docelowa

| # | Źródło | Dostęp | Faza |
|---|--------|--------|------|
| 1 | **platformazakupowa.pl — publiczna wyszukiwarka** `/all?query=...` (sito frazowe) | scraping HTML, **1 żądanie na frazę na run** (robots.txt: Crawl-delay 900); workflow `pz_search.yml` = 6 fraz x 1 żądanie w osobnych godzinach (05:07–10:07). Potwierdzone 2026-08-28: anonimowy dostęp; platforma zwraca WSZYSTKIE aktywne trafienia frazy (limit ignorowany). **Zweryfikowano 2026-08-28 (krok 0.6):** Regulamin platformazakupowa.pl **zakazuje** zautomatyzowane pobieranie treści: „Zakazane jest jakiekolwiek zautomatyzowane pobieranie treści, w szczególności scraping, crawling, TDM lub masowe pobieranie Załączników, z wyjątkiem… udostępnionego przez Usługodawcę API lub innych form udostępniania takich jak pliki CSV… lub bezwzględnie obowiązujących przepisów prawa". Zastrzeżenie TDM z art. 8a ust. 1 ustawy o ochronie baz danych. **Konsekwencja:** cron `pz_search.yml` WYŁĄCZONY; źródło pozostaje jako moduł + workflow_dispatch (ręczne uruchomienia wyłącznie na odpowiedzialność właściciela). Priorytet uzupełnienia luki: BZP (krok 0.2) i inne legalne kanały (powiadomienia e-mail innych platform).
| 2 | **TED** (ted.europa.eu) | REST API v3, bez klucza (sekcja 5) — **działa** | MVP |
| 3 | **BZP / e-Zamówienia** | publiczne API odczytu — **endpoint do potwierdzenia w kroku 0** (sekcja 6); po upadku kanału e-mail BZP awansuje na główne źródło krajowe | MVP |
| 4 | **BIP-y spółek SP** — pilotaż 4–5 spółek | scraping statycznego HTML, osobny parser per spółka (sekcja 7) — PHN **działa** | MVP |
| 5 | ~~platformazakupowa.pl — powiadomienia e-mail (IMAP)~~ | **ODRZUCONE (2026-08-28): platforma nie oferuje subskrypcji powiadomień po kodach CPV** — potwierdzone empirycznie w panelu. Parser `pz_email.py` zostaje dormant (sekcja 4), skrzynka Gmail skonfigurowana i sprawdzona (LOGIN OK) — gotowa na ewentualne powiadomienia z innych platform (Faza 2) | — |
| 6 | Powiadomienia z **innych platform** (ezamawiajacy.pl, SmartPZP, Logintrade) | kanał IMAP + `pz_email.py` (wymaga weryfikacji, czy te platformy oferują powiadomienia) | Faza 2 |
| 7 | ESPI/GPW, SARP, konkursy.org | RSS/HTML | Faza 2 |
| 8 | funduszeeuropejskie.gov.pl | scraping | Faza 3 |

---

## 3. Model danych i scoring

### 3.1 `Announcement`

```
zrodlo            str    # 'platformazakupowa-email' | 'ted' | 'bzp' | 'bip:phn' | ...
tytul             str    # wymagane
zamawiajacy       str
url               str    # wymagane, link do ogłoszenia
data_publikacji   date | None
termin_skladania  datetime | None   # patrz 3.2 — pole istotne funkcjonalnie
opis              str | None        # pełny opis przedmiotu, jeśli źródło dostarcza
cpv               list[str]
score             int
tagi              list[str]
status_opisu      str    # 'brak' | 'pobrany' — sterowanie etapem wzbogacania
hash              str    # sha256(url_znormalizowany + tytul_znormalizowany)
```

### 3.2 `termin_skladania` — pole obowiązkowe funkcjonalnie
Dla biura to drugie najważniejsze pole po tytule: bez niego nie wiadomo, czy da się jeszcze startować. Dostępne w TED (`deadline`), w BZP i zwykle w treści powiadomienia e-mail. Jeśli źródło go nie podaje — `None`, a ogłoszenie oznaczane tagiem `brak-terminu` (widoczne na stronie, nie ukrywane).

### 3.3 Scoring

Liczony osobno na `tytul` (waga ×2) i `opis` (waga ×1). Trafienie w tytule waży więcej, bo tytuł opisuje główny przedmiot zamówienia.

- **Trafienia twarde (+3):** „dokumentacja wielobranżowa", „prace projektowe w zakresie", „dokumentacja projektowa", „dokumentacja projektowo-kosztorysowa", „projektowanie architektoniczne"
- **Konkurs architektoniczny:** +2
- **CPV z `config/cpv.yaml`:** +3
- **Bonusy (+1 każdy):** zamawiający z listy spółek SP/giełdowych w `config/sources.yaml`; frazy „dofinansowanie", „POIiS", „FEnIKS", „KPO"; sektory strategiczne
- **Kary (−3):** frazy drogowo-infrastrukturalne (z zastrzeżeniem wyjątku z sekcji 1)
- **Niski priorytet (−1, bez usuwania):** zamawiający samorządowy (gmina/powiat/urząd/miasto)
- **Progi:** `score >= 3` → publikacja; `score >= 5` → tag `wysoka-trafnosc`

Wszystkie frazy, wagi i progi **wyłącznie** w `config/keywords.yaml`. Kody CPV w `config/cpv.yaml`.

### 3.4 Kalibracja
Progi z 3.3 są punktem startowym, nie wartością docelową. Po 1–2 tygodniach zbierania danych: ręczny przegląd trafień i pominięć, korekta wag w YAML. Zaplanować jako zadanie, nie jako opcję.

---

## 4. Źródło 1: platformazakupowa.pl przez Gmail IMAP

### 4.1 Konfiguracja skrzynki (jednorazowa, ręczna — poza kodem)
1. Nowe konto Gmail wyłącznie do tego celu (np. `przetargi.ozone@gmail.com`).
2. Włączyć **weryfikację dwuetapową** (wymóg Google dla App Password).
3. Wygenerować **App Password** (16 znaków) → do GitHub Secrets jako `GMAIL_APP_PASSWORD`, adres jako `GMAIL_USER`.
4. Na platformazakupowa.pl: konto wykonawcy (bezpłatne), profil opisany **kodami CPV z `config/cpv.yaml`**, adres powiadomień ustawiony na nową skrzynkę.
5. **Powiadomienia muszą trafiać bezpośrednio na tę skrzynkę, nie przez przekazywanie.** Uzasadnienie: `przykład_przetargu.eml` pokazuje, co robi ręczne przekazanie — oryginał OpenNexus zostaje zagnieżdżony jako cytowany blok w wiadomości Outlooka, w quoted-printable i HTML-u z Worda. Parsowanie oryginału jest znacznie prostsze i stabilniejsze.

Sekrety w publicznym repo są bezpieczne (PR-y z forków nie mają do nich dostępu), ale dlatego właśnie skrzynka ma być **dedykowana** — nie firmowa poczta.

### 4.2 Blokada sekwencyjna: fixtures przed parserem
**Nie mamy jeszcze przykładu maila powiadamiającego o nowym postępowaniu.** Posiadany `przykład_przetargu.eml` to powiadomienie o wiadomości na forum w postępowaniu już trwającym — inny szablon.

Kolejność jest więc wymuszona:
1. Skonfigurować skrzynkę (4.1).
2. Odczekać, aż wpłyną **2–3 realne powiadomienia o nowych postępowaniach**, zapisać je jako fixtures w `tests/fixtures/`.
3. **Dopiero wtedy** pisać parser.

W tym czasie implementacja idzie równolegle na źródłach 2–4, które nie są zablokowane (sekcja 9).

### 4.3 Odczyt skrzynki
- `imaplib.IMAP4_SSL('imap.gmail.com', 993)`, login: `GMAIL_USER` + `GMAIL_APP_PASSWORD`
- Wyszukiwanie nieprzeczytanych od nadawcy platformy; po przetworzeniu oznaczyć jako przeczytane (`\Seen`) — to jest naturalny znacznik stanu, **nie trzeba trzymać stanu w repo**
- Nie usuwać wiadomości — skrzynka pozostaje archiwum do debugowania parsera
- Parsowanie: `email` + `email.policy.default`; brać część `text/plain` jeśli istnieje, `text/html` jako fallback (odkodować encje, usunąć tagi)
- Wyciągnąć: tytuł postępowania, zamawiającego, URL (`platformazakupowa.pl/transakcja/{id}`), ID, termin jeśli obecny

### 4.4 Ryzyko: wycofanie App Passwords przez Google
Google promuje OAuth 2.0 i wycofał już „less secure app access". App Passwords działają (wymagają 2FA), ale to ścieżka zachowawcza. **Plan awaryjny, jeśli przestaną działać:** Gmail API z OAuth2 (refresh token w Secrets). Nie implementować teraz — zanotować w README.

### 4.5 Znana luka pokrycia
Powiadomienia są wyzwalane **kodami CPV przypisanymi przez zamawiającego**. Jeśli zamawiający opisze dokumentację wielobranżową kodem robót budowlanych (45\*) zamiast usług projektowych (71\*), maila nie będzie. To jedyna przewaga, jaką zachowuje scraping (wyszukiwanie po frazie w tytule wyłapie to, co CPV pominie). Mitygacja: subskrybować **szeroko** całą grupę 71\* (nadmiar odfiltruje scoring), a sito frazowe wdrożyć w Fazie 2 (źródło 6).

---

## 5. Źródło 2: TED API v3

Konkrety potwierdzone — implementator ich nie zmienia:

- **Endpoint:** `POST https://api.ted.europa.eu/v3/notices/search`
- **Klucz API: niepotrzebny** dla ogłoszeń już opublikowanych (dostęp anonimowy)
- **Body:** `query` (składnia expert search), `fields`, `limit` (≤100), `scope` (`ACTIVE`), `paginationMode: ITERATION`, `page`
- **Składnia zapytania:** `classification-cpv=71220000`, `buyer-country=POL`, `PD>=20260101` (format `YYYYMMDD`), `FT~"dokumentacja wielobranżowa"`, łączenie przez `AND`/`OR`, `SORT BY publication-date DESC`
- **Pola do pobrania:** `publication-number`, `notice-title`, `buyer-name`, `deadline`, `classification-cpv`
- **Uwaga z dokumentacji:** składnia jest **strict**. Zacząć od najprostszego `FT~"..."`, dodawać filtry po jednym i weryfikować odpowiedź. Nie budować pełnego zapytania od razu.
- **Limity dostępu anonimowego nie są udokumentowane** — nie zakładać, że nie istnieją. Zaimplementować backoff (2 próby, rosnący odstęp) i obsługę HTTP 429.

---

## 6. Źródło 3: BZP / e-Zamówienia — wymaga rozstrzygnięcia w kroku 0

**To źródło nie jest jeszcze zweryfikowane.** W obiegu są dwa różne adresy i żaden nie został potwierdzony jako działający:
- `https://ezamowienia.gov.pl/mo-board/api/v1/notice`
- `https://ezamowienia.gov.pl/mo-client-board/api/notices/`

Krok 0 musi rozstrzygnąć empirycznie (`curl`), zapisując wynik w `docs/zrodla-decyzje.md`:
1. Który adres odpowiada i w jakim formacie (JSON/XML)?
2. Czy odczyt naprawdę nie wymaga klucza/rejestracji? (dokumentacja twierdzi, że nie — potwierdzić)
3. **Czy da się filtrować po CPV i po dacie?** Jeśli nie — trzeba pobierać wszystkie ogłoszenia krajowe i filtrować lokalnie, co jest zupełnie innym zadaniem wolumenowo i wymaga przeprojektowania adaptera.
4. Jaki jest dzienny wolumen ogłoszeń?
5. Czy obowiązuje `Regulamin korzystania z API` (media.ezamowienia.gov.pl) i czy nakłada limity?

Dopóki to nie jest rozstrzygnięte, **nie pisać adaptera**.

Zakres merytoryczny: BZP obejmuje zamówienia wg PZP powyżej progu krajowego (130 000 zł) — nie tylko samorządy, także spółki SP działające jako zamawiający publiczni. Ale część spółek prawa handlowego (jak Polski Holding Hotelowy z przykładu) prowadzi postępowania **poza reżimem PZP**, więc BZP i TED **nie zastępują** źródła 1 — uzupełniają je.

---

## 7. Źródło 4: BIP-y spółek SP (pilotaż)

- **Zakres MVP: 4–5 spółek** — PHN S.A. (potwierdzona: `bip.phnsa.pl`, Drupal, statyczne HTML, `Crawl-delay: 10`), KGHM, PGE, PGG, ARP (patrz sekcja 11, pytanie 1 — rozstrzygnięte).
- **Nie zakładać wspólnej struktury HTML.** Każda spółka = osobny plik w `scraper/sources/bip/`, osobny fixture (zapisana kopia strony), osobny test. Wspólny jest tylko interfejs.
- **Przed napisaniem każdego parsera: sprawdzić `robots.txt` danej domeny** i uwzględnić jej `Crawl-delay`. Nie zakładać, że wszędzie jest 10 s jak w PHN — platformazakupowa.pl ma 900 s.
- Skalowanie do 30–50 spółek to **Faza 2**, praca proporcjonalna do liczby spółek. Nie wciągać do MVP.

---

## 8. Architektura, publikacja, niezawodność

### 8.1 Struktura repo

```
scraper/
  sources/
    base.py                  # interfejs: fetch() -> list[Announcement]
    pz_email.py              # źródło 1 (IMAP)
    ted.py                   # źródło 2
    bzp.py                   # źródło 3
    bip/
      phn.py
      <spolka2>.py ...
  filters.py                 # scoring wg keywords.yaml + cpv.yaml, wagi tytul/opis
  dedup.py                   # hash, historia 90 dni
  healthcheck.py             # dwie metryki, patrz 8.4
  site.py                    # generator HTML (Jinja2)
config/
  keywords.yaml
  cpv.yaml
  sources.yaml
data/
  announcements.json
  history/                   # metryki dzienne per źródło (commitowane zawsze — patrz 8.5)
  errors.log
docs/
  zrodla-decyzje.md          # wyniki kroku 0
templates/
  index.html.j2
  archiwum.html.j2
tests/fixtures/
.github/workflows/daily.yml
```

- **Python 3.12**; `httpx`, `selectolax`, `Jinja2`, `PyYAML`. Poczta: `imaplib` + `email` (biblioteka standardowa). **Bez `feedparser`** — v1/v2 zakładały kanały RSS, których istnienia nie potwierdzono.

### 8.2 Jeden workflow, raz dziennie
Architektura z 72 uruchomieniami dziennie **znika razem ze scrapingiem platformazakupowa.pl**. Zostaje jeden `daily.yml`:

- `cron: '7 5 * * *'` — nieokrągła minuta (GitHub kolejkuje pełne godziny z większym opóźnieniem)
- **Harmonogram nie jest gwarantowany:** typowe opóźnienia 5–30 min, przy dużym obciążeniu run może zostać **pominięty bez ponowienia**. „Raz dziennie" oznacza okno, nie punkt. Opisać w README, żeby nikt nie debugował nieistniejącego błędu.
- Dodać `workflow_dispatch` — ręczne uruchomienie do testów i po pominiętym runie
- `concurrency: { group: data-write, cancel-in-progress: false }` — zabezpieczenie przed nałożeniem się runu ręcznego na zaplanowany
- Przed pushem: `git pull --rebase` + retry (2–3 próby)
- Kolejność: pobranie źródeł → scoring → dedup → healthcheck → generowanie strony → commit → Pages

### 8.3 Izolacja awarii
`try/except` **per źródło** (a w źródle 4 — per spółka). Timeout na każde żądanie, retry max 2. Jedno nieudane źródło nie przerywa runu; błąd do `data/errors.log` i do podsumowania Actions jako `::warning::`.

### 8.4 Healthcheck — dwie metryki osobno
Pojedyncza metryka „liczba nowych wyników" daje fałszywe alarmy. Mierzyć rozdzielnie:
- **(a) dostępność:** czy źródło odpowiedziało poprawnie (HTTP 2xx / udany login IMAP). Awaria → `::error::`.
- **(b) wydajność:** średnia liczba wyników na udane odpytanie, porównana z 7-dniową średnią kroczącą z `data/history/`. Spadek >80% → `::warning::` (prawdopodobna zmiana struktury źródła).

Healthcheck **nie blokuje** publikacji — tylko ostrzega. Cel: żeby zepsuty parser nie milczał tygodniami.

### 8.5 Heartbeat — ochrona przed cichym wyłączeniem harmonogramu
GitHub **automatycznie wyłącza scheduled workflows w publicznych repo po 60 dniach bez commitów** (liczą się tylko commity). Ponieważ `announcements.json` commitujemy tylko przy zmianach, możliwy jest samowzmacniający się scenariusz: parsery się psują → brak nowych ogłoszeń → brak commitów → po 60 dniach harmonogram wyłączony → cisza na zawsze, bez żadnego alertu.

**Dlatego `data/history/` jest commitowane przy każdym runie**, niezależnie od tego, czy znaleziono nowe ogłoszenia. To jednocześnie heartbeat i dane dla healthchecku.

### 8.6 Strona www
- GitHub Pages, statyczny HTML, UI po polsku
- Kolumny: termin składania, data publikacji, zamawiający, tytuł (link), score, tagi, źródło
- **Domyślne sortowanie: termin składania rosnąco** (najpilniejsze u góry); ogłoszenia z `brak-terminu` na końcu
- **Okno wyświetlania:** `index.html` pokazuje ogłoszenia z terminem w przyszłości oraz opublikowane w ostatnich 30 dniach. Starsze → `archiwum.html`. Bez tego tabela rośnie bez końca i traci użyteczność.
- Filtrowanie po tagach po stronie klienta (bez frameworka — czysty JS)
- Widoczny znacznik czasu ostatniej aktualizacji i lista źródeł, które w tym runie zawiodły

---

## 9. Kolejność implementacji

**Krok 0 — research, przed kodem** (bez tego implementator zgaduje):
- 0.1 Ustalić finalną listę kodów CPV dla usług projektowych/architektonicznych (dział 71 — m.in. 71200000, 71220000, 71221000, 71222000, 71240000, 71300000, 71320000, 71400000; **potwierdzić w oficjalnym słowniku CPV**, nie przyjmować tej listy na wiarę) → `config/cpv.yaml`
- 0.2 Rozstrzygnąć endpoint i możliwości filtrowania API BZP (sekcja 6) → `docs/zrodla-decyzje.md`
- 0.3 Wskazać 4–5 spółek SP na pilotaż BIP
- 0.4 Skonfigurować Gmail + konto wykonawcy + subskrypcję CPV (4.1) → **częściowo niewykonalne: subskrypcja CPV nie istnieje na platformie** (sekcja 11 pyt. 2); Gmail skonfigurowany i przetestowany (LOGIN OK), parser dormant
- 0.5 (NOWE) URL publicznej wyszukiwarki platformazakupowa.pl: **`/all?page=&limit=&query=`** — potwierdzony anonimowy dostęp (2026-08-28), fixture: `tests/fixtures/pz_search.html`; **do decyzji właściciela: zgodność scrapingu z Regulaminem platformy**

**Ścieżka A — niezablokowana, start od razu:**
1. Szkielet repo, `requirements.txt`, pliki `config/*.yaml`, model `Announcement`
2. `filters.py` + testy jednostkowe — w tym **test wyjątku „wraz z niezbędną infrastrukturą"** i test scoringu na tytule z `przykład_przetargu.eml` („Wykonanie szczegółowej, wielobranżowej dokumentacji projektowo-kosztorysowej dla obiektu sanatoryjnego w Kołobrzegu" — oczekiwany wynik: publikacja)
3. Adapter TED (sekcja 5)
4. Adapter BZP — **tylko po rozstrzygnięciu 0.2**
5. Adaptery BIP: PHN + pozostałe pilotażowe (osobne pliki, osobne fixtures)
6. `dedup.py` + zapis `data/announcements.json`
7. `healthcheck.py` (8.4)
8. `site.py` + szablony (8.6)
9. `daily.yml` (8.2) + publikacja Pages
10. README: dodawanie źródeł i słów kluczowych, ograniczenia harmonogramu (8.2), plan awaryjny dla App Password (4.4)

**Ścieżka B — zablokowana do czasu zebrania fixtures (4.2):**
11. Parser powiadomień e-mail + adapter `pz_email.py` — **dopiero po zebraniu 2–3 realnych maili**

**Faza 2:** parsery powiadomień z innych platform (ezamawiajacy.pl, SmartPZP, Logintrade); sito frazowe dla luki CPV (4.5); skalowanie BIP do 30–50 spółek; ESPI/GPW, SARP.
**Faza 3:** funduszeeuropejskie.gov.pl.

---

## 10. Zasady dla implementatora

1. Każde źródło = osobny moduł, wspólny interfejs `fetch() -> list[Announcement]`.
2. Konfiguracja (frazy, CPV, spółki, progi, wagi) **tylko w YAML**, nigdy w kodzie.
3. Nie zgadywać adresów API ani struktury HTML. Każdy parser pisany przeciw **zapisanemu fixture**, nie przeciw żywej stronie.
4. Przed parserem nowego źródła: sprawdzić `robots.txt` tej domeny i uszanować `Crawl-delay`.
5. Sekrety (`GMAIL_USER`, `GMAIL_APP_PASSWORD`) **tylko** z GitHub Secrets. Nigdy w kodzie, configu ani logach. Nie logować treści maili z danymi konta.
6. Commity i logi po angielsku; treść strony po polsku.
7. Bez LLM w runtime.
8. Limit czasu `daily.yml`: ≤ 10 min. Generowanie strony < 1 s.
9. Jeśli specyfikacja jest niejednoznaczna — **zgłosić, nie improwizować**.

---

## 11. Pytania otwarte

1. **Które 4–5 spółek SP na pilotaż BIP** poza PHN? **ROZSTRZĄŚNIĘTE:** pilotaż = PHN S.A. (potwierdzona), KGHM Polska Miedź S.A. (sekcja „Przetargi" istnieje; URL do potwierdzenia w kroku 0), PGE S.A. (strony ogłoszeń spółek grupy istnieją, ale holding głównie przez Logintrade — ta część przejdzie kanałem IMAP), Polska Grupa Górnicza S.A. i ARP S.A. (obie do potwierdzenia w kroku 0). Rezerwa: Tauron S.A. Odrzucone: PKP S.A. (HTTP 403, anty-bot), Wody Polskie (infrastruktura — poza profilem, 11 rozproszonych stron RZGW), PGZ (systemy zamknięte). Szczegóły: `docs/zrodla-decyzje.md`.
2. Czy w panelu platformazakupowa.pl subskrypcja pozwala **tylko na kody CPV**, czy także na własne frazy kluczowe? Jeśli frazy są dostępne, luka pokrycia z 4.5 znacząco się zmniejsza i sito frazowe (źródło 6) może być zbędne. **ROZSTRZĄŚNIĘTE NEGATYWNIE (2026-08-28): subskrypcja e-mail CPV/fraz nie istnieje.** Rozwiązanie: publiczna wyszukiwarka `/all?query=` jako źródło 1 (sito frazowe w MVP); IMAP dormant.

## 12. Referencje

- Ogłoszenie na BIP spółki SP: https://bip.phnsa.pl/ogloszenia/2
- `przykład_przetargu.eml` — powiadomienie z platformazakupowa.pl/OpenNexus, **ręcznie przekazane**; użyteczne jako test scoringu tytułu (krok A2), **nie** jako fixture parsera e-maili (4.2)
- TED API: https://docs.ted.europa.eu/api/latest/index.html
- e-Zamówienia, integracja: https://ezamowienia.gov.pl/pl/integracja/
- Regulamin platformazakupowa.pl: https://platformazakupowa.pl/strona/45-regulamin
