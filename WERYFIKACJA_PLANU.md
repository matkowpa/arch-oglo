# Weryfikacja planu (PLAN.md) — ustalenia i rekomendacje

Poniżej weryfikacja techniczna `PLAN.md` względem `TODOs.txt`. Ogólna architektura (moduły per źródło, scoring w YAML, GitHub Pages + Actions) jest sensowna i dobrze dopasowana do "taniego" implementatora. Znalazłem jednak kilka konkretnych, sprawdzonych faktów, które podważają założenia w sekcjach 2 i 4 planu i wymagają korekty przed rozpoczęciem implementacji.

## 1. Krytyczne ustalenia (sprawdzone)

### 1.1 platformazakupowa.pl — limit `Crawl-delay: 900` koliduje z limitem 10 min w GH Actions
Sprawdzony `robots.txt` serwisu zawiera `Crawl-delay: 900` (15 minut między requestami) dla domyślnego User-Agenta, przy stronie wyników (`/all`) mającej ~3862 aktywne postępowania rozłożone na ~129 stron. Nawet zawężając zapytania do kilku-kilkunastu fraz kluczowych, uczciwe respektowanie tego crawl-delay wymaga **godzin**, a nie minut — wprost sprzeczne z zapisem w PLAN.md pkt 5.7 ("scrape ≤ 10 min").

Dodatkowo: od **10 grudnia 2025** obowiązuje nowy regulamin platformy, który — wg zapowiedzi OpenNexus — doprecyzowuje zasady dot. **automatyzacji i wykorzystania danych/treści**. Treści tego zapisu nie udało się potwierdzić w pełni (research nie dotarł do konkretnego paragrafu), ale sam fakt, że temat automatyzacji został świeżo uregulowany, oznacza, że **trzeba przeczytać aktualny regulamin przed budową scrapera**, a nie zakładać "RSS + scraping HTML" jako rzecz oczywistą.

**Rekomendacja:** nie traktować platformazakupowa.pl jako źródła "burst scrape raz dziennie". Warianty:
- (a) rozbić pobieranie na cały dzień — osobny, lekki workflow uruchamiany co 15-20 min, każdorazowo 1 request (mieści się w crawl-delay), stan zapisywany przyrostowo;
- (b) ograniczyć się do wyszukiwania przez pole search z konkretnymi frazami z `keywords.yaml` (mniej stron) i nadal rozłożyć w czasie;
- (c) rozważyć kontakt z OpenNexus o oficjalny feed/API zamiast scrapingu — to jedyna droga do realnego "raz dziennie w 10 minut".
Plan powinien jawnie wybrać jeden z wariantów, bo obecny zapis ("RSS + scraping HTML", limit 10 min) jest wewnętrznie sprzeczny.

### 1.2 BZP w planie wskazuje nieaktualny adres i jest błędnie zdegradowany do Fazy 2
PLAN.md opisuje źródło #5 jako `bzp1.portal.gov.pl`, "głównie samorządy", niski priorytet, z dopiskiem "bywa odporna na boty". To nieaktualne: od 2021 r. ogłoszenia BZP (progi krajowe 130 000 zł – progi unijne) są udostępniane przez **Platformę e-Zamówienia** (`ezamowienia.gov.pl`), a stary portal BZP nie jest już właściwym źródłem.

Co ważniejsze: e-Zamówienia udostępnia **oficjalne, publiczne, bezautoryzacyjne API** do odczytu ogłoszeń BZP (`.../mo-board/api/v1/notice` — wg dokumentacji odczyt ogłoszeń i statystyk BZP "nie wymaga przechodzenia procedury integracyjnej"), a część danych jest też dostępna w standardzie **OCDS** (Open Contracting Data Standard) — czyli strukturalnie, bez parsowania HTML. To jest z definicji łatwiejsze, tańsze i stabilniejsze niż scraping BIP-ów (patrz 1.3), więc nie powinno być w Fazie 2 jako "plan B", tylko **w MVP jako pełnoprawne źródło**, obok TED.

Uwaga do zakresu: BZP obejmuje zamówienia objęte PZP powyżej progu krajowego — nie tylko samorządy. Sam fakt "spółka skarbu państwa" nie gwarantuje jednak obecności w BZP/TED — część spółek prawa handlowego (jak w przykładowym mailu: Polski Holding Hotelowy) prowadzi postępowania **poza reżimem PZP** (na platformach komercyjnych typu platformazakupowa.pl), bo nie każda spółka SP kwalifikuje się jako "zamawiający publiczny" dla każdego zakupu. To znaczy: **BZP/TED nie zastępują scrapingu BIP/platform komercyjnych — są źródłem uzupełniającym**, nie alternatywnym. Plan powinien to rozróżnienie nazwać wprost, bo obecnie sugeruje (błędnie), że BZP to głównie "niższa liga" gmin.

**Rekomendacja:** przenieść "e-Zamówienia / BZP API" do MVP (obok TED), zaktualizować URL/opis, dodać notatkę o regulaminie API (`Regulamin korzystania z API`, PDF na media.ezamowienia.gov.pl) do sprawdzenia przed integracją.

### 1.3 TED API — potwierdzone, plan trafny
Publiczne API TED (`docs.ted.europa.eu/api`) rzeczywiście umożliwia anonimowe wyszukiwanie po kraju, CPV i dacie. Ten fragment planu (MVP, priorytet średni) jest poprawny i nie wymaga zmian, poza jednym: warto zweryfikować dokładną listę kodów CPV przed implementacją (712xxxxx ma więcej podkodów niż tylko "71200000-2 / 71300000-0 / 71400000-3" — np. 71220000 "Usługi projektowania architektonicznego" może być bardziej precyzyjny niż nadrzędny kod 71200000). To 30-minutowe zadanie researchowe, ale warto je nazwać explicite w kroku 1 implementacji, żeby tani model nie zgadywał kodów.

### 1.4 BIP-y spółek SP — realny nakład pracy jest niedoszacowany
Plan traktuje "BIP-y spółek skarbu państwa" jako jeden moduł (`sources/bip_spolki.py`) z listą 30-50 spółek w YAML. W praktyce każda spółka (PGE, KGHM, ARP, PFR, PGW, PHN...) ma **inną strukturę strony/BIP** — nie ma jednego wspólnego szablonu (poza ew. spółkami na tym samym silniku BIP, co trzeba dopiero sprawdzić). To oznacza de facto dziesiątki mikro-parserów, nie jeden moduł z jednym selektorem CSS — sprawdzony przykład (`bip.phnsa.pl`, Drupal, `Crawl-delay: 10`) jest łatwy, ale nie ma podstaw by zakładać, że pozostałe 29-49 spółek jest równie proste.

**Rekomendacja:** w MVP ograniczyć listę BIP do 3-5 spółek (w tym PHN jako sprawdzony przykład), z jasnym mechanizmem "jedna spółka = jeden plik parsera dziedziczący po wspólnym interfejsie, ale bez zakładania wspólnego selektora". Rozszerzanie do 30-50 spółek przenieść do osobnego, policzalnego etapu (Faza 2), bo to praca proporcjonalna do liczby spółek, nie stała.

### 1.5 Harmonogram GitHub Actions cron nie jest precyzyjny
Potwierdzone: GitHub nie gwarantuje wykonania `schedule: cron` o dokładnej minucie — typowe opóźnienia to 5-30 min (szczyt o pełnych godzinach), odnotowywano też przypadki kilkugodzinnych opóźnień lub pominiętych uruchomień przy dużym obciążeniu platformy. Zalecenie społeczności: planować cron na nieokrągłą minutę (np. `7 5 * * *` zamiast `0 5 * * *`).

**Rekomendacja:** zmienić `cron: '0 5 * * *'` na nieokrągłą minutę i jawnie zaakceptować (w README/PLAN.md), że "raz dziennie" oznacza "w oknie ok. godziny", a nie punktualnie — inaczej przy debugowaniu ktoś będzie szukał nieistniejącego błędu.

## 2. Ustalenia projektowe (bez researchu, z przeglądu logiki planu)

### 2.1 Reguła wyjątku "niezbędna infrastruktura" jest niedospecyfikowana
Plan poprawnie identyfikuje wymóg z TODOs.txt (fraza "wraz z niezbędną infrastrukturą" nie może wykluczać ogłoszenia), ale nie mówi, **na jakim polu** działa scoring: sam tytuł ogłoszenia, czy pełny opis przedmiotu zamówienia? To ma znaczenie — dokument może w tytule mieć "dokumentacja wielobranżowa", a w opisie dalszym "budowa sieci wodociągowej" jako główny przedmiot. Model `Announcement` w planie nie rozróżnia `tytuł` od `opis`/pełnej treści.

**Rekomendacja:** dodać do modelu `Announcement` osobne pola `tytul` i `opis` (jeśli dostępny z danego źródła), i ważyć trafienia z tytułu wyżej niż z opisu — inaczej reguła "wyjątku" będzie działać przypadkowo w zależności od tego, gdzie akurat w tekście padło dane słowo.

### 2.2 Brak mechanizmu wykrywania "cichej" awarii scrapera
Plan ma try/except per źródło (dobrze), ale nie ma sanity-checku typu "źródło X zwróciło 0 wyników / drastycznie mniej niż zwykle → oznacz jako podejrzane". Scraping HTML psuje się cicho przy zmianie struktury strony — bez tego, użytkownik dowie się o awarii dopiero jak zauważy pustą stronę.

**Rekomendacja:** dodać krok w `filters.py`/`site.py`: porównanie liczby wyników z danego źródła do średniej kroczącej (np. 7 dni); przy spadku >80% — log ostrzegawczy widoczny na stronie/w podsumowaniu run'u GH Actions (np. jako `::warning::` w Actions).

### 2.3 "Bez LLM w runtime" — trafne dla kosztów, ale warto nazwać limit tego podejścia
Czysty regex/scoring jest tani i deterministyczny — słuszny wybór przy tanim modelu implementującym. Trzeba się jednak liczyć z tym, że rozróżnienie „prace projektowe drogowe” vs „dokumentacja wielobranżowa obejmująca m.in. drogi wewnętrzne" będzie czasem błędne. To nie wymaga zmiany planu teraz, ale warto zapisać wprost (w README) że próg `score >= 3` będzie wymagał kalibracji na rzeczywistych przykładach (w tym na `przykład_przetargu.eml`) po zebraniu pierwszych 1-2 tygodni danych, a nie tylko raz na starcie.

## 3. Podsumowanie zmian do naniesienia w PLAN.md

| # | Zmiana | Priorytet |
|---|--------|-----------|
| 1 | platformazakupowa.pl: zmienić strategię pobierania (rozłożenie w czasie / wyszukiwanie po frazach), sprawdzić regulamin z 10.12.2025 | Wysoki — blokuje MVP w obecnym kształcie |
| 2 | BZP: zaktualizować z `bzp1.portal.gov.pl` na `ezamowienia.gov.pl` + API BZP, przenieść z Fazy 2 do MVP | Wysoki |
| 3 | BIP spółek SP: zredukować MVP do 3-5 spółek, jasno nazwać koszt skalowania do 30-50 | Średni |
| 4 | CPV: zweryfikować pełną listę kodów 71xxxxxx przed implementacją adaptera TED | Niski (szybkie do zrobienia) |
| 5 | Cron: przesunąć na nieokrągłą minutę, opisać w README niepewność czasu wykonania | Niski |
| 6 | Model `Announcement`: rozdzielić `tytul`/`opis` do ważenia scoringu | Średni |
| 7 | Dodać sanity-check "cichej awarii" źródła | Średni |

## 4. Otwarte pytania do właściciela projektu

1. Czy akceptujesz, że pobieranie z platformazakupowa.pl będzie rozłożone na cały dzień (przez crawl-delay), zamiast jednego szybkiego joba rano?
2. Czy mamy sprawdzić/przeczytać nowy regulamin platformazakupowa.pl (grudzień 2025) przed pisaniem scrapera — czy wolisz najpierw spróbować i reagować, jeśli coś zablokują?
3. Którą listę 3-5 spółek SP wziąć jako pilotaż BIP (poza PHN)?
