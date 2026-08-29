Stwórz jeden gotowy plik HTML z Tailwind CSS oraz prostym JavaScriptem dla strony Arch-Ogło (bazy ogłoszeń architektonicznych).

STYLISTYKA (STRICT):
- Dark mode: tło `bg-zinc-950`, karty `bg-zinc-900`, tekst `text-zinc-100` i `text-zinc-400`.
- Ramki: `border border-zinc-800`, zaokrąglenia `rounded-xl`.
- Akcent: kolor szmaragdowy (badge `bg-emerald-500/10 text-emerald-400`).

STRUKTURA STRONY:
1. Nawigacja: Przyklejony pasek na górze z logo "Arch-Ogło" oraz przyciskami filtrowania:
   - `<button data-filter="all">Wszystkie</button>`
   - `<button data-filter="konkurs">Konkursy</button>`
   - `<button data-filter="praca">Praca</button>`
   - `<button data-filter="przetarg">Przetargi</button>`
2. Hero Section: Nagłówek "Baza Ogłoszeń Architektonicznych" i 3 karty ze statystykami.
3. Główny Grid:
   - Lewa kolumna: Min. 4 karty ogłoszeń. Każda karta ma atrybut `data-category` (np. `data-category="konkurs"`), badge kategorii, tytuł, miejsce oraz badge z czasem.
   - Prawa kolumna: Panel "Pilne terminy" z listą 3 najbliższych wydarzeń.
4. Footer: Minimalistyczna stopka.

LOGIKA JAVASCRIPT (Na końcu pliku w tagu <script>):
Napisz prosty skrypt, który:
1. Nasłuchuje kliknięć w przyciski filtrów w nawigacji.
2. Po kliknięciu zmienia styl aktywnego przycisku (np. dodaje tło `bg-emerald-500` / `text-white`).
3. Filtruje karty ogłoszeń w lewej kolumnie na podstawie atrybutu `data-category`: ukrywa niepasujące (klasa `hidden`), a pokazuje wybrane. Dla przycisku "all" pokazuje wszystkie karty.

Zrób kompletny, działający kod gotowy do uruchomienia w przeglądarce (z dołączonym Tailwind CDN).