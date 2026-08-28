# Weryfikacja PLAN_V2.md — uwagi

Krytyczny przegląd [PLAN_V2.md](PLAN_V2.md). Uwaga: weryfikuję tu własny plan, więc celowo szukałem w nim błędów, a nie potwierdzeń. Znalazłem **jedną wewnętrzną sprzeczność**, **jedno błędne założenie o kosztach** i **jedną pominiętą alternatywę architektoniczną, która może być lepsza od tego, co zaproponowałem**.

Szkielet planu (modularne źródła, scoring w YAML, GitHub Pages, krok 0 jako research) oceniam jako dobry i wart zachowania. Problemy koncentrują się w sekcji 4.2 — czyli w najbardziej „wynalazczej" części, którą sam dopisałem w v2.

---

## A. Krytyczne — wymagają decyzji przed implementacją

### A1. Sekcja 4.2 opiera się na założeniu o cronie, które sam wcześniej podważyłem

`platformazakupowa-poll.yml` z `cron: '*/20 * * * *'` zakłada 72 regularne odpalenia dziennie. Fakty:

- Harmonogram GitHub Actions **nie jest gwarantowany**: typowe opóźnienia 5–30 min.
- Przy opóźnieniu ≥20 min slot zderza się z następnym i **run jest pomijany bez retry** — „if a fire is scheduled for 09:00 and the platform does not get to it before 10:00, the 09:00 fire is gone".
- Interwały krótsze niż 5 min są cicho koalescowane lub ignorowane (nie dotyczy nas bezpośrednio, ale pokazuje, jak luźno GitHub traktuje minutową precyzję).

**To jest sprzeczność wewnętrzna:** w [WERYFIKACJA_PLANU.md](WERYFIKACJA_PLANU.md) pkt 1.5 sam napisałem, że cron jest niepewny — a potem w PLAN_V2 zbudowałem na nim mechanizm wymagający 72 regularnych odpaleń. Skutek praktyczny: round-robin po frazach będzie miał nieprzewidywalne pokrycie; część fraz nie zostanie sprawdzona w danym dniu w ogóle, i nie będzie o tym żadnej informacji.

**Rekomendacja:** nie polegać na regularności odpaleń. Rotacja fraz musi być odporna na pominięcia — zamiast round-robin „następna fraza z kolejki", użyć **priorytetu wg najstarszego sprawdzenia** (każda fraza ma `last_checked`; run bierze frazę najdłużej niesprawdzoną). Wtedy nieregularne odpalenia degradują świeżość, ale nie tworzą fraz-sierot.

### A2. „Koszt zerowy" jest nieprawdziwy dla repozytorium prywatnego

Rachunek, którego w planie nie zrobiłem:

- 72 runy/dzień × 30 dni = **2160 runów/miesiąc**
- GitHub **zaokrągla każdy job w górę do pełnej minuty** (job 5-sekundowy kosztuje 1 minutę)
- → minimum **2160 minut/miesiąc** z samego pollingu, plus `daily.yml`
- Darmowy limit planu Free dla repo **prywatnego: 2000 minut/miesiąc**

Czyli plan **przekracza darmowy limit** i generuje realny koszt (~$0,006/min Linux 2-core powyżej limitu). Zerowy koszt zachodzi tylko dla repozytorium **publicznego** (nielimitowane minuty).

Ale repo publiczne oznacza, że **publiczna staje się lista słów kluczowych i śledzonych spółek** — czyli wprost strategia akwizycyjna biura architektonicznego, informacja konkurencyjnie wrażliwa. Plan nie nazywa tego wyboru ani nie podejmuje decyzji.

**Rekomendacja:** to decyzja użytkownika, nie implementatora — patrz pytanie 1 w sekcji D. Uwaga: architektura z A1/A5 (mniej runów) albo z B1 (ingest e-mail, brak pollingu) tę presję kosztową w dużej mierze likwiduje.

### A3. Throttling „wymuszony w kodzie" w moim planie nie może działać

Sekcja 4.2 mówi jednocześnie dwie niekompatybilne rzeczy:

- pkt 3: commit **tylko jeśli są nowe pozycje** (żeby nie zaśmiecać historii),
- pkt 4: kod wymusza minimalny odstęp między requestami, stan w `data/pz_state.json`.

Runner GitHuba jest efemeryczny — jedyna pamięć między runami to repozytorium. Jeśli poll nie znajdzie nic nowego i nie zrobi commita, **timestamp ostatniego requestu nie zostaje zapisany**. Następny run nie wie, kiedy był poprzedni request → throttling w kodzie jest fikcją dokładnie w najczęstszym scenariuszu (brak nowych ogłoszeń).

**Rekomendacja:** rozdzielić dane od stanu. Stan (`last_request_at`, `last_checked` per fraza) trzymać w **GitHub Actions cache** albo commitować **zawsze** do osobnego pliku stanu na osobnej gałęzi (np. `state`), tak by historia gałęzi głównej pozostała czysta. Dane (`announcements.json`) commitować tylko przy zmianach — jak w planie.

### A4. Dwa workflowy piszą do tego samego pliku na tej samej gałęzi — nieuchronne konflikty push

`daily.yml` i `platformazakupowa-poll.yml` oba commitują `data/announcements.json`. Plan nie ma ani `concurrency:` group, ani strategii na `rejected (non-fast-forward)`. Przy 72 runach dziennie kolizja z runem dziennym jest kwestią dni, nie miesięcy.

**Rekomendacja:** dodać `concurrency: { group: data-write, cancel-in-progress: false }` do oba workflowów oraz pętlę `pull --rebase` + retry (2–3 próby) przed pushem. To 10 linii, ale bez tego pipeline będzie losowo tracić dane.

### A5. Sekcja 3 wymaga pola `opis`, którego architektura 4.2 nie jest w stanie pobrać

Najpoważniejszy błąd logiczny w planie. Sekcja 3 wprowadza rozdzielenie `tytul`/`opis` z ważeniem — i uzasadniam to właśnie regułą wyjątku „wraz z niezbędną infrastrukturą". Ale:

- dla platformazakupowa.pl jedyny dozwolony request na run to **strona listy** → dostępne są **tylko tytuły**,
- pobranie `opis` wymaga wejścia w `/transakcja/{id}` = **kolejny request** = złamanie zasady „jeden request na run" i `Crawl-delay: 900`.

Skutek: `opis` będzie **zawsze puste** dla tego źródła, a mechanizm ważenia tytuł/opis — którym uzasadniałem całą zmianę modelu danych — nie zadziała tam, gdzie jest najbardziej potrzebny (bo to właśnie platformazakupowa.pl dostarcza ogłoszenia typu z przykładu użytkownika).

**Rekomendacja:** przyjąć jawnie, że wzbogacanie o `opis` jest **osobnym, kolejkowanym etapem**: ogłoszenie trafia najpierw do `announcements.json` ze statusem `opis_pending`, a kolejne runy pollingu dociągają opisy dla pozycji o wysokim score z tytułu (kolejka priorytetowa, 1 request/run, ten sam throttling). Scoring liczony dwuetapowo: wstępny z tytułu, finalny po dociągnięciu opisu. Alternatywnie — patrz B1, gdzie problem nie występuje.

---

## B. Pominięta alternatywa architektoniczna

### B1. Ingest e-maili zamiast scrapingu — prawdopodobnie prostszy i bezpieczniejszy

Przykład użytkownika (`przykład_przetargu.eml`) dowodzi rzeczy, której nie wykorzystałem w planie: **biuro już otrzymuje powiadomienia z platformazakupowa.pl na skrzynkę e-mail**. Zamiast scrapować portal, można subskrybować kategorie/branże na koncie wykonawcy i parsować dedykowaną skrzynkę (IMAP lub alias przekazujący).

Porównanie z mechanizmem z sekcji 4.2:

| | Scraping throttled (4.2) | Ingest e-mail (B1) |
|---|---|---|
| `Crawl-delay: 900` | wymusza całą architekturę pollingu | **nie dotyczy** |
| Ryzyko regulaminowe (nowy regulamin 10.12.2025) | otwarte, blokujące | **znikome** — normalne użycie serwisu |
| Model | pull, nieregularny (A1) | **push, natychmiastowy** |
| Koszt GH Actions | 2160+ min/mies. (A2) | 1 run dziennie |
| Stan/throttling/konflikty | A3, A4 | **nie występują** |
| Kruchość | zmiana HTML listy psuje parser | zmiana szablonu maila psuje parser |
| Pokrycie | teoretycznie całość portalu | **tylko subskrybowane kategorie** |

Główny minus: pokrycie zależy od poprawnie ustawionych subskrypcji na koncie (i od tego, czy portal oferuje subskrypcję ogłoszeń, a nie tylko powiadomień w postępowaniach, w których już się uczestniczy — **to trzeba sprawdzić w kroku 0**). Dla pozostałych źródeł (TED, BZP, BIP-y) nic się nie zmienia — one mają API/statyczne HTML i nie mają problemu crawl-delay.

**Rekomendacja:** rozstrzygnąć to **przed** implementacją kroku 6, bo B1 usuwa jednocześnie A1, A2, A3, A4 i A5. Jeśli subskrypcja ogłoszeń jest dostępna, to jest ścieżka domyślna, a scraping — plan B.

---

## C. Uwagi merytoryczne i uzupełnienia

### C1. Brak terminu składania ofert w modelu `Announcement` — dziura funkcjonalna
Model ma datę, zamawiającego, tytuł, opis, URL, score, tagi, źródło, CPV, hash — ale **nie ma terminu składania ofert/wniosków**. Dla biura to prawdopodobnie drugie najważniejsze pole po tytule: bez niego użytkownik nie wie, czy jeszcze może startować. Dane są dostępne w obu głównych źródłach (lista `/all` pokazuje „Deadline timestamp"; TED API ma pole `deadline`). **Dodać `termin_skladania` do modelu i jako kolumnę na stronie, z sortowaniem.**

### C2. TED — plan jest zbyt ogólny, a konkrety są znane (sprawdzone)
Plan mówi tylko „publiczne API". Tani model będzie zgadywał. Do wpisania dosłownie:
- `POST https://api.ted.europa.eu/v3/notices/search` (v3 to wersja aktualna; v2 wspierana do czasu v4), **bez klucza** dla ogłoszeń opublikowanych
- body: `query` (składnia expert search), `fields`, `limit` (≤100), `scope` (`ACTIVE`/`ALL`), `paginationMode: ITERATION`, `page`
- składnia: `classification-cpv=71220000`, `buyer-country=POL`, `PD>=20260101`, `FT~"dokumentacja wielobranżowa"`, `AND`/`OR`, `SORT BY publication-date DESC`
- pola m.in.: `publication-number`, `notice-title`, `buyer-name`, `deadline`
- **Ostrzeżenie z dokumentacji:** składnia jest strict — testować od prostego `FT~"..."` i dodawać filtry po jednym.
- Limity/quoty dla dostępu anonimowego **nie są udokumentowane** — nie zakładać, że są nieograniczone; dodać własny backoff.

### C3. BZP — endpoint nie jest potwierdzony, a plan traktuje go jako pewnik
W źródłach krążą **dwa różne adresy**: `ezamowienia.gov.pl/mo-board/api/v1/notice` oraz `ezamowienia.gov.pl/mo-client-board/api/notices/`. Próba pobrania drugiego nie zwróciła danych (tylko nagłówek strony). Osobno: **nie udało się potwierdzić, że API BZP pozwala filtrować po CPV** — jeśli nie pozwala, trzeba ściągać wszystkie ogłoszenia krajowe i filtrować lokalnie, co jest zupełnie innym zadaniem wolumenowo.

Krok 0.2 w planie brzmi „sprawdzić czy wymaga klucza" — **za mało**. Musi rozstrzygnąć empirycznie (`curl`): (a) który URL działa, (b) format odpowiedzi, (c) czy da się filtrować po CPV i dacie, (d) jaki wolumen dzienny. Dopiero to pozwala oszacować adapter. Awans BZP do MVP (z v1→v2) był słuszny co do intencji, ale plan przedstawia to źródło jako pewniejsze, niż faktycznie zweryfikowałem.

### C4. `przykład_przetargu.eml` nie jest fixture dla parsera HTML (błąd przeniesiony z v1)
Punkt 5.3 planu każe testować adapter platformazakupowa.pl na tym pliku. Ale to e-mail o **nowej wiadomości na forum w już trwającym postępowaniu**, nie ogłoszenie z listy przetargów. Nadaje się jako fixture dla `filters.py` (tekst tytułu → scoring) i dla ewentualnego parsera e-maili (B1), **nie** dla parsera HTML listy. Rozdzielić te dwa zastosowania w planie.

### C5. Cichy tryb awarii: brak commitów → GitHub wyłącza harmonogram
Dla repo **publicznych** GitHub automatycznie wyłącza scheduled workflows po **60 dniach bez commitów** (liczą się tylko nowe commity, nie issues/PR-y). Plan commituje tylko przy nowych pozycjach — więc scenariusz „źródła zamilkły / parser się zepsuł → brak commitów → po 60 dniach harmonogram wyłączony → cisza na zawsze, bez alertu" jest realny i samowzmacniający. **Rekomendacja:** zawsze commitować `data/history/` (heartbeat healthchecku), niezależnie od tego, czy znaleziono nowe ogłoszenia.

### C6. Krok 0.1 powinien być bramką decyzyjną, nie zadaniem do odhaczenia
Plan każe przeczytać regulamin platformazakupowa.pl, ale krok 6 (adapter) jest wpisany bezwarunkowo w kolejność implementacji. Jeśli regulamin zabrania automatyzacji, praca z kroku 6 idzie do kosza. **Zapisać jawnie:** „jeśli regulamin zabrania automatycznego pobierania → pominąć 4.2 i krok 6, przejść na B1 (ingest e-mail); jeśli B1 też niedostępne → eskalować do właściciela projektu".

### C7. `healthcheck.py` będzie generował fałszywe alarmy
Porównanie liczby nowych wyników do 7-dniowej średniej kroczącej nie zadziała dla platformazakupowa.pl w trybie throttled: dzienna liczba wyników zależy głównie od tego, **ile runów faktycznie odpaliło** (A1), a to jest z natury szumne. **Rekomendacja:** mierzyć dwie metryki osobno — (a) liczba udanych requestów vs. oczekiwana, (b) średnia liczba wyników per udany request. Alarmować na (b), raportować (a).

### C8. Brak okna wyświetlania / archiwizacji na stronie
Plan definiuje 90-dniową historię dla dedupu, ale nie mówi, **co pokazuje strona**. Bez tego tabela rośnie bez końca i traci użyteczność. **Propozycja:** domyślny widok = ogłoszenia z terminem składania w przyszłości + opublikowane w ostatnich 30 dniach; resztę do `archiwum.html`. Wymaga C1 (pole terminu).

---

## D. Pytania do rozstrzygnięcia przed implementacją

Kolejność ma znaczenie — odpowiedź na 1 i 2 zmienia architekturę, nie detale.

1. **Repo publiczne czy prywatne?** Publiczne = koszt zerowy, ale jawna lista słów kluczowych i śledzonych spółek (strategia akwizycyjna biura). Prywatne = poufność, ale przy architekturze z 4.2 przekroczenie darmowego limitu 2000 min/mies. (A2).
2. **Czy idziemy ścieżką ingest e-mail (B1) zamiast scrapingu platformazakupowa.pl?** Usuwa naraz pięć problemów (A1–A5). Wymaga sprawdzenia w kroku 0, czy portal oferuje subskrypcję *ogłoszeń* (a nie tylko powiadomień z postępowań, w których biuro już bierze udział) — i dedykowanej skrzynki/aliasu.
3. Które 3–5 spółek SP na pilotaż BIP, poza PHN? (pytanie otwarte z v1, wciąż bez odpowiedzi)
4. Czy dodajemy `termin_skladania` jako pole obowiązkowe i główną kolumnę sortowania? (C1 — zakładam „tak", ale to zmienia model danych i szablon strony)

---

## E. Podsumowanie: co zostaje, co się zmienia

**Zostaje bez zmian (oceniam jako trafne):** krok 0 jako oddzielna faza research, modularne źródła z jednym interfejsem, scoring deterministyczny w YAML bez LLM w runtime, awans BZP do MVP (co do intencji), redukcja BIP-ów do pilotażu, healthcheck jako koncepcja, cron na nieokrągłą minucie dla `daily.yml`.

**Do przepisania:** cała sekcja 4.2 (A1, A3, A4, A5) — albo naprawiona zgodnie z rekomendacjami, albo zastąpiona przez B1.

**Do uzupełnienia:** model danych (C1), konkrety TED (C2), zakres kroku 0.2 (C3), fixtures (C4), heartbeat (C5), gate regulaminowy (C6), metryki healthchecku (C7), okno wyświetlania (C8).

**Wniosek:** PLAN_V2.md nie jest gotowy do przekazania tanemu modelowi w obecnej formie — sekcja 4.2 zawiera sprzeczne wymagania (A3, A5), które implementator albo zrealizuje błędnie, albo zablokuje się na nich. Sugeruję rozstrzygnąć pytania D1–D2 i wydać PLAN_V3.md.
