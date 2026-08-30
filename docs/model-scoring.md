## Model scoringu: deterministyczny vs statystyczny (decyzja 2026-08-30)

**Wybór: model deterministyczny (Python + regex + YAML), bez LLM i bez uczenia statystycznego.** Uzasadnienie:

1. **Brak danych treningowych.** Model statystyczny (NB/logreg na tytułach) potrzebuje etykietowanych przykładów „trafi/nie trafi" — zebranie setek etykiet wymaga miesięcy używania i ręcznej adnotacji.
2. **Deterministyczny jest audytowalny:** każdemu punktowi widać źródło (frazę/CPV/tag) — kluczowe przy kalibracji typu „dlaczego to ogłoszenie ma score 3".
3. **Skala problemu jest mała** (~50 opublikowanych pozycji/run) — ręczny przegląd + korekta wagi to koszt minuty, a nie trening modelu.
4. Plan (sekcja 10.7) zakłada „bez LLM w runtime"; model statystyczny wpisuje się w tę lukę kosztowniej (serwis, drift, monitoring dryfu) bez korzyści przy wolumenie 400–500 rekordów/dobę.

**Ewolucja zamiast rewolucji** — gdyby reguły stały się zbyt kruche, ścieżka rozwoju (od najtańszej):
1. **Wzbogacenie cech deterministycznych** (np. podział tytułu TED na segmenty „Polska – kategoria CPV – przedmiot" i ważenie tylko segmentu przedmiotowego; frazy w opisie z `htmlBody` BZP),
2. **Kolekcjonowanie etykiet** (tag „nieistotne" na stronie → feedback loop) — dopiero wtedy model statystyczny ma na czym się uczyć,
3. Ostatecznie: mały lokalny klasyfikator (np. logreg na TF-IDF tytułów), ale dopiero przy ≥ kilkuset oznaczonych przykładach i wyraźnym opóźnieniu jakości heurystyk.
