---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "goal-standard",
  "kind": "information",
  "version": 2,
  "title": "Goal contract catalog and extraction standard",
  "status": "draft",
  "owner": "wellmanifest/goal",
  "created": "2026-09-14",
  "updated": "2026-09-14",
  "review_after": "2026-10-14",
  "source_revision": "4d8b4d286d2ceaa8bab3e948d5cceb7e89f5b5ca",
  "affected_repositories": ["wellmanifest/goal"],
  "evidence": [
    "https://github.com/semcod/goal/commit/4d8b4d286d2ceaa8bab3e948d5cceb7e89f5b5ca",
    "https://github.com/wellmanifest/new-project/blob/d54878a105a20d84dd554f205bc177dcacc8730a/governance/standard-packs.json",
    "https://github.com/wellmanifest/performance/blob/0fbf213c6c9b0e103e228496e879cc3ff9a21f09/README.md"
  ]
}
---

# Standard wellmanifest/goal 0.1.0 — projekt do przeglądu

<!-- docs:section purpose -->
## Cel

Sformalizować kontrakty już obecne w Goal tak, aby można je było niezależnie
sprawdzać i stopniowo przekazywać istniejącym pakietom Wellmanifest. Ten pakiet
jest właścicielem **formatu katalogu i procesu ekstrakcji**, nie drugim
właścicielem semantyki Git, ticketów, autoryzacji lub merge. Runtime pozostaje
w `semcod/goal`. Nie kopiujemy CLI, daemonów ani implementacji recovery.

<!-- docs:section scope -->
## Zakres i granica normatywna

Normatywne dla konsumenta tego projektu standardu są reguły CAT-001–CAT-008
poniżej i [model katalogu](../../models/catalog.schema.json).
[Katalog WMGOAL](../standard/catalog.json) zawiera **opisowe obserwacje** zachowania
Goal i proponowane miejsca ekstrakcji. Jego zdania nie nadpisują polityk
właścicieli. `mapped` oznacza mapowanie, nie zakończone przekazanie własności.

Wersja 0.1.0 obejmuje 12 zaobserwowanych kontraktów i jedną jawnie niewdrożoną
propozycję budżetów. Nie certyfikuje wszystkich modułów Goal. Poza zakresem są
m.in. wykonanie aktualizacji zależności, routing modeli, wszystkie ścieżki
interaktywnego recovery oraz rzeczywista konfiguracja floty i CI.

<!-- docs:section evidence -->
## Dowody

Obserwacje odnoszą się wyłącznie do Goal w rewizji
`4d8b4d286d2ceaa8bab3e948d5cceb7e89f5b5ca`, nie do ruchomego `main` ani do
zainstalowanej globalnie wersji CLI. Każdy zapis obserwowany wskazuje plik,
SHA-256 i symbol implementacji; 11 z 12 wskazuje też symbol testu. WMGOAL-008
ma w tej wersji tylko dowód źródłowy, bez przypisanego testu.

Własność domen oparto na katalogu `new-project` przypiętym osobno od Goal.
Zakres `performance` ma osobny przypięty odnośnik do README właściciela.
To dowód istnienia zakresów, nie zgoda tych właścicieli na konkretną ekstrakcję.
Checker weryfikuje hashe i istnienie symboli bez importowania kodu źródłowego;
nie dowodzi prawdziwości każdego zdania ani uruchomienia wskazanego testu.

<!-- docs:section content -->
## Kontrakty i właściciele docelowi

| Identyfikatory | Kontrakt Goal | Docelowy pakiet |
| --- | --- | --- |
| WMGOAL-001, 009, 011 | Tryby dostarczania, baza wydania, projekcje wersji | `wellmanifest/git-lifecycle` |
| WMGOAL-002 | Jednoznaczne powiązanie z ticketem | `wellmanifest/ticket-lifecycle` |
| WMGOAL-003 | Lokalna zdolność wykonania push: token, termin, tryb, remote | `wellmanifest/authority-lifecycle` |
| WMGOAL-004, 005, 007 | Opublikowana adopcja, wspierany pin, kontrola źródła standardu | `wellmanifest/new-project` |
| WMGOAL-006 | Kody diagnostyczne i bezpieczne odnośniki do runbooków | `wellmanifest/logs` |
| WMGOAL-008 | Reconciliation jako wynik do przeglądu, nie zgoda na usunięcie | `wellmanifest/merge` |
| WMGOAL-010 | Zachowanie pracy przez konkretny helper recovery | `wellmanifest/repair-lifecycle` |
| WMGOAL-012, 013 | Stałe limity prób i propozycja adaptacyjnego budżetu | `wellmanifest/performance` |

`validation-attestation` pozostaje właścicielem zaufanego dowodu review;
lokalna zdolność push z WMGOAL-003 nie zastępuje tego kontraktu. `worktrees`
pozostaje właścicielem układu checkoutów. Ich reguł nie kopiujemy do katalogu
jako nowej semantyki Goal tylko dlatego, że Goal wywołuje ich checkery.

### Wymagania konsumenta katalogu

1. **CAT-001 — Tożsamość i źródło.** MUSI zachować stabilne ID, unikatowy
   zakres `concern`, pełną rewizję źródła, hash pliku i wskazany symbol.
   NIE WOLNO używać ruchomego `latest` jako dowodu historycznego zachowania.
2. **CAT-002 — Jeden właściciel.** MUSI wskazać jeden proponowany pakiet
   docelowy na zakres. Mapowanie nie przenosi własności. Istniejący kontrakt
   właściciela ma pierwszeństwo przed opisowym skrótem w katalogu.
3. **CAT-003 — Obserwacja a propozycja.** `observed` MUSI mieć dowód implementacji;
   `proposed` NIE MOŻE udawać wdrożonej funkcji. V1 nie obsługuje statusu
   `extracted`; jego użycie zostaje odrzucone, zamiast potwierdzać przekazanie
   bez kontraktu dowodowego. Brak testu pozostaje widoczną luką.
4. **CAT-004 — Brak uprawnień.** Katalog, wynik checkera, hash i nazwa standardu
   NIE udzielają uprawnień do push, merge, usunięcia, sekretów ani deploymentu.
   Wynik pozytywny MUSI zachować `effectAuthority=false` i odróżniać walidację
   struktury od weryfikacji źródła i zachowania runtime.
5. **CAT-005 — Kompatybilność.** Nowa publikacja standardu NIE wymusza masowej
   adopcji. Istniejący poprawny pin pozostaje podstawą pracy, dopóki chroniona
   polityka właściciela nie ustali inaczej. Nieznana wersja katalogu zatrzymuje
   interpretację tego katalogu, nie daje podstaw do samowolnego zatrzymania
   niezależnych zadań produktu. Upgrade odbywa się w osobnym bounded scope.
6. **CAT-006 — Diagnostyka.** Narzędzie MUSI emitować JSON i stabilny kod.
   `WMGOAL-INPUT-001`: sprawdź JSON, duplikaty i limit rozmiaru;
   `WMGOAL-CONTRACT-001`: sprawdź model, ID, właściciela i status;
   `WMGOAL-SOURCE-001`: dostarcz właściwe lokalne repozytoria z przypiętymi
   obiektami Git i zweryfikuj cytowanie. NIE zmieniaj hashy tylko po to, aby
   przejść kontrolę. Aktualizacja dowodu wymaga przeglądu zmienionego kontraktu.
7. **CAT-007 — Bez wykonania.** Checker MUSI działać offline i nie uruchamiać
   wskazanych implementacji, przepisów migracyjnych, poleceń z katalogu ani LLM.
   Limit wejścia to 1 MiB, a liczba reguł nie przekracza 128. Limit chroni
   interpretację katalogu i nie jest limitem budżetu zadania produktu.
8. **CAT-008 — Ewolucja.** Zmiana znaczenia kontraktu wymaga nowej wersji;
   historyczne ID i źródła pozostają odtwarzalne w Git. Przy ekstrakcji
   zachowuje się mapowanie starego ID do kanonicznego kontraktu właściciela.
   Nie wolno usuwać starej definicji przed testem kompatybilności odbiorców.

### Bezpieczna kolejność ekstrakcji

1. Wybierz jeden zakres, porównaj rzeczywistą semantykę z istniejącym pakietem
   i ustal, czy potrzebna jest zmiana właściciela, czy tylko odnośnik.
2. W repozytorium właściciela przygotuj mały ticket: kontrakt, wspólne wektory
   pozytywne i negatywne, historyczny odczyt, kryteria akceptacji i rollback.
3. Po niezależnej akceptacji przypnij opublikowaną rewizję i hash. Sam PR,
   lokalny PASS i deklaracja w katalogu nie wystarczają.
4. W Goal przygotuj adapter lub projekcję tego przypięcia. Porównaj stare i nowe
   wyniki dla tych samych wektorów, w tym exit codes, zakresów i odmów.
5. Dopiero po tej weryfikacji zmień katalog na kompatybilny odnośnik. Format
   przyszłego dowodu zakończenia ekstrakcji należy przyjąć z właścicielem;
   nie dodawać nieobsługiwanego `extracted=true` do V1.

Warunek zatrzymania: konflikt semantyki, brak opublikowanego kontraktu,
niezgodne stare dane lub brak wymaganej akceptacji. Pozostałe rozłączne prace
mogą trwać. Rollback przywraca poprzedni pin i adapter bez przepisywania historii.

### Uruchomienie

```sh
python operations/conformance.py
python -m unittest discover -s operations -p 'test_*.py' -v
./project/governance-check.sh --base main --head HEAD --actor agent
```

Opcjonalne sprawdzenie dokładnych źródeł, bez fetch i wykonywania ich kodu:

```sh
python operations/conformance.py \
  --source-root /path/to/semcod/goal \
  --routing-root /path/to/wellmanifest/new-project \
  --performance-root /path/to/wellmanifest/performance
```

Exit `0` oznacza zgodność sprawdzanych danych; `2` odmowę lub niepełne wejście.
Bez trzech repozytoriów `sourceEvidenceVerified` pozostaje `false`. Wbudowany
walidator obsługuje wyłącznie podzbiór JSON Schema użyty przez ten model;
nieobsługiwane słowo kluczowe jest błędem, nie ignorowanym wymaganiem.

<!-- docs:section limitations -->
## Ograniczenia i ryzyka

Repozytorium [wellmanifest/goal](https://github.com/wellmanifest/goal) jest publiczne
na wyraźne polecenie użytkownika. Standard 0.1.0 pozostaje projektem do przeglądu,
nie wydaniem. Nie potwierdzono niezależnego review, wdrożonej kontroli kontraktów
ani adopcji przez Goal. Standard nie dowodzi, że stare recovery
jest bezpieczne jako całość: inne strategie zawierają działania destrukcyjne.
Stash nie jest trwałym snapshotem cross-machine. Stałe limity prób i TTL
nie dowodzą istnienia adaptacyjnego zarządzania budżetem.

WMGOAL-013 jest propozycją: można dostosować przepustowość w zatwierdzonej
obwiedni na podstawie pomiarów i braku konfliktów. Nie wolno zwiększać
uprawnień, terminów ważności dowodów lub pomijać akceptacji dla oszczędności
czasu. Implementacja i pomiary takiego kontrolera pozostają osobnym zadaniem.

Przypięty checker ciągłości `new-project` wymaga `remote.origin.url`.
Przed zgodą na publikację jego brak uniemożliwiał prawidłowy checkpoint V2;
zachowano wtedy historię lokalną i zewnętrzny snapshot, bez fikcyjnego remote.
Po utworzeniu rzeczywistego repozytorium granicę publikacji można zapisać
standardowym checkpointem. Historyczny snapshot nie staje się przez to
automatycznie poprawnym checkpointem V2 ani dowodem zdalnej akceptacji.

<!-- docs:section next_actions -->
## Następne działania

Przejrzeć katalog z właścicielami przed merge; uzupełnić test WMGOAL-008;
wybrać pierwszy zakres ekstrakcji. Chroniony rejestr Validatora i profil OneDev
nie obejmowały wellmanifest/goal podczas preflight publikacji. Ich przyjęcie
wymaga osobnej, zaufanej konfiguracji; kod autora nie nadaje sobie akceptacji.
Nie ma
automatycznej adopcji ani przepisania istniejących standardów w tym zadaniu.
