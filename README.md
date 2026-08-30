# arch-oglo — agregator ogłoszeń przetargowych

**🌐 Wyniki publikowane na:** **https://matkowpa.github.io/arch-oglo/**
(Strona wymaga jednorazowego włączenia: GitHub → Settings → Pages → Source: *GitHub Actions*. Archiwum: https://matkowpa.github.io/arch-oglo/archiwum.html)

Codzienne zbieranie ogłoszeń o przetargach na **prace projektowe architektury / dokumentację wielobranżową** (spółki SP, projekty UE, sektory strategiczne) i publikacja na GitHub Pages. Specyfikacja: [final_plan.md](final_plan.md).

## Szybki start (lokalnie)

```bash
pip install -r requirements.txt
python -m pytest tests          # testy
python -m scraper.run           # pełny run: źródła -> scoring -> dedup -> strona
# wynik: data/announcements.json, docs_site/index.html, docs_site/archiwum.html
```

## Kanał e-mail (IMAP) — rezerwa

Parser powiadomień e-mail (`scraper/sources/pz_email.py`) jest gotowy, ale
wyłączony — platformazakupowa.pl nie oferuje subskrypcji powiadomień po CPV.
Zostaje jako rezerwa na wypadek włączenia powiadomień na innych platformach
(Logintrade, ezamawiajacy.pl) w Fazi 2. Skrzynka i sekrety (`GMAIL_USER`,
`GMAIL_APP_PASSWORD`) pozostają skonfigurowane.

## Źródła

> Kafelek „N źródeł danych" na [stronie głównej](https://matkowpa.github.io/arch-oglo/)
> linkuje do tej sekcji. Liczba N = liczba unikalnych źródeł wśród aktualnie
> wyświetlanych ogłoszeń (pełna lista aktywnych źródeł poniżej).

| Źródło | Status | Uwagi |
|---|---|---|
| **platformazakupowa.pl — wyszukiwarka `/all?query=`** | ✅ **AKTYWNY** | 6 fraz x 1 żądanie/dzień (`pz_search.yml`, godziny 05–10 UTC, odstęp 60 min ≫ `Crawl-delay: 900`). Platforma zwraca wszystkie aktywne trafienia frazy. Awaria źródła nie wpływa na pozostałe (izolacja w run.py). |
| TED API v3 | **AKTYWNY** | anonimowy POST `/v3/notices/search`; pola wielojęzyczne (preferuje `pol`) |
| **BZP / e-Zamówienia** | ✅ **AKTYWNY** (od 2026-08-29) | anonimowy GET `/mo-board/api/v1/notice` (NoticeType=ContractNotice, okno publikacji 1 dzień); API nie filtruje po CPV → filtr lokalny wg `config/cpv.yaml`; termin = `submittingOffersDate`; szczegóły: [docs/zrodla-decyzje.md](docs/zrodla-decyzje.md) |
| BIP: PHN S.A. | **AKTYWNY** (od 2026-08-28) | `bip.phnsa.pl/ogloszenia/1..3` (paginacja 3 stron), Crawl-delay 10 |
| BIP: Grupa TAURON (SWOZ) | **AKTYWNY** (od 2026-08-29) | `swoz.tauron.pl/.../current/list` (platforma Mercus, server-side, ~30 najnowszych); robots.txt: brak; szczegóły: [docs/zrodla-decyzje.md](docs/zrodla-decyzje.md) |
| BIP: KGHM S.A. | **AKTYWNY** (od 2026-08-29) | `kghm.com/pl/przetargi-nieograniczone` (Drupal views, 2 × 10 najnowszych); właściwy URL odkryty sondu (plan zgłaszał 404) |
| BIP: PGG | **ODŁOŻONY** | listy zakupowe renderowane w JS (pusty `<main>`); do powrotu po znalezieniu endpointu JSON |
| BIP: pozostałe spółki (ARP/Enea/JSW/Orlen/Intercity) | **ZAMKNIĘTE** | werdykt sondy z runnera (bip-probe #1): DNS nie istnieje / WAF 403 / timeout — brak ścieżki scrapingu |
| PSE (`przetargi.pse.pl`) / PGE (Logintrade) | **TIER B / FAZA 2** | jedyny żywy kandydat kolejnego źródła: research API PSE |
| platformazakupowa (IMAP) | **WYŁĄCZONY** | platforma NIE oferuje subskrypcji CPV e-mail (potwierdzone 2026-08-28); parser dormant na powiadomienia z innych platform (Faza 2) |
Dodawanie źródła: nowy plik w `scraper/sources/` z klasą `fetch() -> list[Announcement]` + wpis w `config/sources.yaml`.

### Kody CPV

Wspólna lista **9 kodów z działu 71** (CPV 2008, usługi architektoniczne / inżynieryjne / projektowe — pełna tabela z opisami: [zrodla.md](zrodla.md), konfiguracja: `config/cpv.yaml`) steruje wszystkimi źródłami klasyfikowanymi po CPV:

- **TED** — kody w zapytaniu strict (`classification-cpv IN (...)`) — filtrowanie po stronie TED,
- **BZP** — API nie filtruje po CPV, więc ta sama lista stosowana lokalnie do pobranych ogłoszeń.

Weryfikacja (krok 0.1): każdy kod potwierdzony przez API TED (nieznane kody TED odrzuca); szczegóły w komentarzu `config/cpv.yaml`. Dokumentuje też, które kody są celowo **poza** listą (np. 71247000 — nadzór nad budową) — poszerzenie to edycja `query` w `config/sources.yaml`.


## Troubleshooting

**Błąd „pages build and deployment" / Jekyll `chdir: No such file or directory - docs`**
W repo mogą istnieć **dwa równoległe deploymenty Pages**: nasz (`daily-scrape` →
`deploy-pages`, publikuje artefakt `docs_site`) oraz wbudowany workflow GitHuba
`pages-build-deployment`, który buduje Jekyll ze źródła `./docs` (brak tam strony —
błąd nieszkodliwy, ale zaśmieca Actions i może wysyłać maile o błędach).
Naprawa: **Settings → Pages → Build and deployment → Source: GitHub Actions** —
wbudowany workflow zniknie, a `deploy-pages` pozostanie jedynym mechanizmem
publikacji. Odwrotna konfiguracja (*Deploy from a branch*) powoduje, że `deploy-pages`
zaczyna padać — nie mieszaj obu trybów.

## Reguły filtrowania (sekcje 1, 3.3)

- Twarde frazy +3 (×waga pola: tytuł ×2, opis ×1), konkurs +2, CPV 71* +3
- Bonus: spółki SP/giełdowe, UE (POIiS/FEnIKS/KPO), sektory strategiczne
- Kary −3×waga: drogi (`drogow`, `autostrad`…), sieci/infrastruktura (`kanalizac`, `wodociąg`…)
- Kara łagodna −1×waga: „roboty budowlane" (kalibracja 2026-08-30 — obniża ranking, nie wyklucza; tag `roboty-budowlane`)
- **Wyjątek:** „wraz z niezbędną infrastrukturą" ±120 znaków blokuje karę infrastrukturalną
- Samorządy −1 (niżej, nie usuwane). Publikacja: score ≥ 3; „wysoka trafność": ≥ 5
- Wszystko w `config/keywords.yaml`, `config/cpv.yaml`, `config/weights.yaml`
- **Re-scoring całości:** każdy run ocenia na nowo cały magazyn — zmiany wag/fraz działają wstecz (wpisy spadające poniżej progu znikają)

## Harmonogram

GitHub Actions `.github/workflows/daily.yml`: cron `7 5 * * *` (UTC). **Harmonogram nie jest gwarantowany** — opóźnienia 5–30 min, run może zostać pominięty (użyj workflow_dispatch). `data/history/` jest commitowany przy każdym runie = heartbeat przeciw wyłączeniu cron po 60 dniach bez commitów.

## Kroki 0 (research) — status

- [x] 0.3 spółki pilotażowe (PHN, KGHM, PGE, PGG, ARP) — patrz final_plan.md sekcja 11
- [x] 0.4 struktura Gmail opisana (wymaga ręcznej konfiguracji przez właściciela)
- [x] 0.1 potwierdzenie listy CPV — każdy kod zweryfikowany przez API TED (słownik CPV 2008), patrz komentarz w config/cpv.yaml
- [x] 0.2 rozstrzygnięcie endpointu BZP — potwierdzony empirycznie 2026-08-29, adapter włączony; patrz docs/zrodla-decyzje.md
