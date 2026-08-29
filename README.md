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

| Źródło | Status | Uwagi |
|---|---|---|
| **platformazakupowa.pl — wyszukiwarka `/all?query=`** | ✅ **AKTYWNY** | 6 fraz x 1 żądanie/dzień (`pz_search.yml`, godziny 05–10 UTC, odstęp 60 min ≫ `Crawl-delay: 900`). Platforma zwraca wszystkie aktywne trafienia frazy. Awaria źródła nie wpływa na pozostałe (izolacja w run.py). |
| TED API v3 | **AKTYWNY** | anonimowy POST `/v3/notices/search`; pola wielojęzyczne (preferuje `pol`) |
| **BZP / e-Zamówienia** | ✅ **AKTYWNY** (od 2026-08-29) | anonimowy GET `/mo-board/api/v1/notice` (NoticeType=ContractNotice, okno publikacji 1 dzień); API nie filtruje po CPV → filtr lokalny wg `config/cpv.yaml`; termin = `submittingOffersDate`; szczegóły: [docs/zrodla-decyzje.md](docs/zrodla-decyzje.md) |
| BIP: PHN S.A. | **AKTYWNY** | `bip.phnsa.pl/ogloszenia/1..3` (paginacja 3 stron), Crawl-delay 10 |
| platformazakupowa (IMAP) | **WYŁĄCZONY** | platforma NIE oferuje subskrypcji CPV e-mail (potwierdzone 2026-08-28); parser dormant na powiadomienia z innych platform (Faza 2) |

Dodawanie źródła: nowy plik w `scraper/sources/` z klasą `fetch() -> list[Announcement]` + wpis w `config/sources.yaml`.

## Reguły filtrowania (sekcje 1, 3.3)

- Twarde frazy +3 (×waga pola: tytuł ×2, opis ×1), konkurs +2, CPV 71* +3
- Bonus: spółki SP/giełdowe, UE (POIiS/FEnIKS/KPO), sektory strategiczne
- Kary −3×waga: drogi (`drogow`, `autostrad`…), sieci/infrastruktura (`kanalizac`, `wodociąg`…)
- **Wyjątek:** „wraz z niezbędną infrastrukturą" ±120 znaków blokuje karę infrastrukturalną
- Samorządy −1 (niżej, nie usuwane). Publikacja: score ≥ 3; „wysoka trafność": ≥ 5
- Wszystko w `config/keywords.yaml`, `config/cpv.yaml`, `config/weights.yaml`

## Harmonogram

GitHub Actions `.github/workflows/daily.yml`: cron `7 5 * * *` (UTC). **Harmonogram nie jest gwarantowany** — opóźnienia 5–30 min, run może zostać pominięty (użyj workflow_dispatch). `data/history/` jest commitowany przy każdym runie = heartbeat przeciw wyłączeniu cron po 60 dniach bez commitów.

## Kroki 0 (research) — status

- [x] 0.3 spółki pilotażowe (PHN, KGHM, PGE, PGG, ARP) — patrz final_plan.md sekcja 11
- [x] 0.4 struktura Gmail opisana (wymaga ręcznej konfiguracji przez właściciela)
- [x] 0.1 potwierdzenie listy CPV — każdy kod zweryfikowany przez API TED (słownik CPV 2008), patrz komentarz w config/cpv.yaml
- [x] 0.2 rozstrzygnięcie endpointu BZP — potwierdzony empirycznie 2026-08-29, adapter włączony; patrz docs/zrodla-decyzje.md
