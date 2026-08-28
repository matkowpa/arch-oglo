# arch-oglo — agregator ogłoszeń przetargowych

Codzienne zbieranie ogłoszeń o przetargach na **prace projektowe architektury / dokumentację wielobranżową** (spółki SP, projekty UE, sektory strategiczne) i publikacja na GitHub Pages. Specyfikacja: [final_plan.md](final_plan.md).

## Szybki start (lokalnie)

```bash
pip install -r requirements.txt
python -m pytest tests          # testy
python -m scraper.run           # pełny run: źródła -> scoring -> dedup -> strona
# wynik: data/announcements.json, docs_site/index.html, docs_site/archiwum.html
```

## Konfiguracja Gmail (źródło 1 — sekcja 4.4 final_plan.md)

1. Dedykowane konto Gmail + 2FA + **App Password**.
2. GitHub Secrets: `GMAIL_USER`, `GMAIL_APP_PASSWORD`.
3. Na platformazakupowa.pl: konto wykonawcy, profil z kodami CPV (config/cpv.yaml), powiadomienia **bezpośrednio** na nową skrzynkę (nie przez przekazywanie).
4. Zebrać 2–3 realne powiadomienia o nowych postępowaniach → `tests/fixtures/pz_*.eml` → dopiero wtedy produkcyjnie włączyć parser (sekcja 4.2 — blokada sekwencyjna).

## Źródła

| Źródło | Status | Uwagi |
|---|---|---|
| **platformazakupowa.pl — wyszukiwarka `/all?query=`** | ⛔ **WYŁĄCZONY (decyzja prawna)** | Regulamin (zweryfikowany 2026-08-28) **zakazuje zautomatyzowanego pobierania treści** (scraping/crawling/TDM; wyjątki: oficjalne API/CSV; zastrzeżenie TDM z art. 8a ustawy o ochronie baz danych). Cron zakomentowany w `pz_search.yml` — reaktywacja wyłącznie świadomą decyzją właściciela. |
| TED API v3 | **AKTYWNY** | anonimowy POST `/v3/notices/search`; pola wielojęzyczne (preferuje `pol`) |
| BIP: PHN S.A. | **AKTYWNY** | `bip.phnsa.pl/ogloszenia/1` (paginacja 1..3), Crawl-delay 10 |
| platformazakupowa (IMAP) | **WYŁĄCZONY** | platforma NIE oferuje subskrypcji CPV e-mail (potwierdzone 2026-08-28); parser dormant na powiadomienia z innych platform (Faza 2) |
| BZP / e-Zamówienia | **WYŁĄCZONY** (`sources.yaml: bzp.enabled: false`) | do rozstrzygnięcia kroku 0.2; po upadku kanału e-mail — główne źródło krajowe |

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
- [ ] 0.1 potwierdzenie listy CPV w oficjalnym słowniku (lista robocza w config/cpv.yaml)
- [ ] 0.2 rozstrzygnięcie endpointu BZP (adapter celowo wyłączony)
