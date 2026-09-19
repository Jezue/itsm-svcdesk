<!-- ai-generated: 100% - AI drafted the specification from the published course requirements and checks. -->
# Specyfikacja usługi `svcdesk` — Laboratory 1

## 1. Cel i zakres

`svcdesk` jest pojedynczą usługą HTTP/JSON do rejestrowania i obsługi zgłoszeń service desk. Usługa nadaje zgłoszeniom priorytet na podstawie wpływu i pilności, pilnuje ich cyklu życia oraz oblicza terminy SLA. Wszystkie requesty i odpowiedzi z body używają `application/json`. Wszystkie znaczniki czasu są chwilami RFC 3339, porównywanymi jako punkty w czasie, a usługa zwraca je w UTC z końcówką `Z`.

Niniejsza specyfikacja jawnie przyjmuje rozstrzygnięcia konfliktów: **C1: `wallclock`**, **C2: `immutable`**, **C3: `matrix`**.

## 2. Reprezentacja zgłoszenia

Zgłoszenie zwracane przez API zawiera co najmniej:

- `id`: niepusty, unikatowy napis nadany przez usługę;
- `title`: wymagany tytuł od 1 do 200 znaków;
- `description`: opcjonalny opis od 0 do 4000 znaków, domyślnie pusty napis `""`;
- `impact` i `urgency`: liczby całkowite od 1 do 3;
- `reporter`: obiekt z wymaganym `name` od 1 do 100 znaków, opcjonalnym `email` typu napis lub `null` (domyślnie `null`) i opcjonalnym logicznym `vip` (domyślnie `false`);
- `priority`: jedna z wartości `P1`, `P2`, `P3`, `P4`, wyliczona przez usługę;
- `state`: `new`, `acknowledged`, `in_progress`, `resolved` albo `closed`;
- `created_at` oraz, gdy dana czynność już nastąpiła, odpowiednio `acknowledged_at`, `resolved_at` i `closed_at`;
- `related_to`: opcjonalny identyfikator wcześniejszego zgłoszenia lub `null`, domyślnie `null`; w Lab 1 wskazany identyfikator nie jest walidowany, w szczególności usługa nie sprawdza istnienia powiązanego zgłoszenia;
- `sla`: obiekt zawierający co najmniej `ack_due_at` i `resolve_due_at`.

Pola czasu dotyczące czynności są `null` albo nieobecne przed wykonaniem tych czynności. Odpowiedzi błędów są JSON-em z obiektem najwyższego poziomu `error`, na przykład `{ "error": { "code": "validation", "message": "title is required" } }`; konkretne wartości `code` nie stanowią kontraktu Lab 1.

## 3. Endpointy

### `GET /health`

Zwraca `200 OK` i JSON `{ "status": "ok", "service": "svcdesk" }`, gdy proces jest gotowy do obsługi żądań. Odpowiedź może zawierać dodatkowe pola. Nieistniejąca trasa zwraca `404 Not Found` z body JSON; niewłaściwa metoda dla istniejącej trasy może zwrócić 404 albo 405.

### `POST /tickets`

Tworzy zgłoszenie. Wymagany JSON zawiera `title`, `impact`, `urgency` oraz `reporter` z polem `name`. Opcjonalne pola to `description`, `reporter.email`, `reporter.vip` i `related_to`, z wartościami domyślnymi opisanymi w rozdziale 2. `impact` i `urgency` muszą być liczbami całkowitymi należącymi do zbioru `{1, 2, 3}`.

Pola należące do serwera — `id`, `priority`, `state`, `created_at`, `acknowledged_at`, `resolved_at`, `closed_at` i `sla` — przesłane w requeście są po cichu ignorowane. Tak samo ignorowane są wszystkie pola nieznane. Nie powodują one błędu i nie mogą nadpisać wartości wyliczonych lub nadanych przez usługę.

Sukces zwraca `201 Created` i kompletne zgłoszenie w stanie `new`, z nowym identyfikatorem, `created_at`, wyliczonym `priority`, wartościami domyślnymi pól opcjonalnych oraz oboma terminami SLA. Brak wymaganego pola, pusty lub dłuższy niż 200 znaków tytuł, opis dłuższy niż 4000 znaków, pusta lub dłuższa niż 100 znaków nazwa reportera, `impact` lub `urgency` poza zakresem (w szczególności `impact: 5`), wartość niecałkowita (w szczególności `urgency: "high"`), inny nieprawidłowy typ lub niepoprawny JSON zwracają `400 Bad Request` albo `422 Unprocessable Entity`, z obiektem `error`.

### `GET /tickets/{id}`

Zwraca `200 OK` i zgłoszenie o podanym identyfikatorze. Nieznany identyfikator zwraca `404 Not Found` z polem `error`.

### `GET /tickets`

Zwraca `200 OK` i tablicę wszystkich pasujących zgłoszeń w dowolnej kolejności, bez paginacji. Opcjonalne parametry `state` i `priority` filtrują wynik odpowiednio po dokładnej wartości stanu i priorytetu. Po podaniu filtra tablica nie może zawierać zgłoszeń niespełniających filtra; brak wyników oznacza pustą tablicę.

### Operacje zmiany stanu

- `POST /tickets/{id}/ack`: dozwolone wyłącznie dla `new`; zwraca `200 OK`, stan `acknowledged` i ustawia `acknowledged_at` na bieżący czas żądania.
- `POST /tickets/{id}/start`: dozwolone wyłącznie dla `acknowledged`; zwraca `200 OK` i stan `in_progress`.
- `POST /tickets/{id}/resolve`: dozwolone wyłącznie dla `in_progress`; zwraca `200 OK`, stan `resolved` i ustawia `resolved_at` na bieżący czas żądania.
- `POST /tickets/{id}/close`: dozwolone wyłącznie dla `resolved`; zwraca `200 OK`, stan `closed` i ustawia `closed_at` na bieżący czas żądania.
- `POST /tickets/{id}/reopen`: dla `resolved` jest dozwolone, gdy `now <= resolved_at + 7 dni`, i zwraca `200 OK` ze stanem `in_progress`; czyści `resolved_at` i `closed_at`, ale zachowuje pierwotny `resolve_due_at`; po upływie okna zwraca `409 Conflict`.

Każda udana akcja zwraca kompletne zgłoszenie. Operacja wykonana ze stanu, z którego nie ma odpowiadającego przejścia, zwraca `409 Conflict` z obiektem `error` i nie zmienia zgłoszenia. Dotyczy to między innymi: ponownego potwierdzenia, rozpoczęcia `new`, rozwiązania `new` lub `acknowledged`, zamknięcia `new` lub `in_progress` i ponownego otwarcia `new`. Akcja na nieznanym identyfikatorze zwraca `404 Not Found` z obiektem `error`.

### `GET /tickets/{id}/sla`

Zwraca `200 OK` i bieżący stan SLA zgłoszenia w postaci `{ priority, ack_due_at, resolve_due_at, ack_breached, resolve_breached, paused }`. Trzy ostatnie pola są logiczne. Nieznane zgłoszenie zwraca `404 Not Found` z obiektem `error`.

## 4. Macierz priorytetów i VIP (C3)

Wartość 1 oznacza największy wpływ lub pilność, a 3 najmniejszy. Priorytet jest zawsze wyliczany według macierzy:

| impact \\ urgency | 1 | 2 | 3 |
|---|---|---|---|
| 1 | P1 | P2 | P3 |
| 2 | P2 | P3 | P4 |
| 3 | P3 | P4 | P4 |

Zgodnie z **C3: `matrix`**, status VIP reportera nie podwyższa priorytetu. Zgłoszenie VIP o `impact=3`, `urgency=3` pozostaje `P4`, a VIP o wartościach `(1,1)` pozostaje `P1`. Także przy VIP pole `priority` z requestu jest ignorowane.

## 5. Cykl życia, zamykanie i niezmienność (C2)

Podstawowa sekwencja stanów to:

`new -> acknowledged -> in_progress -> resolved -> closed`

Jedyną drogą wstecz jest `resolved -> in_progress` przez `reopen`, o ile `now` nie jest późniejsze niż `resolved_at + 7 dni`. Przykładowo ponowne otwarcie po 6 dniach oraz dokładnie na granicy 7 dni jest dozwolone, a po 7 dniach i 1 sekundzie nie jest. Ponowne otwarcie czyści `resolved_at` i `closed_at`; nie wylicza ponownie i nie przesuwa pierwotnego `resolve_due_at`.

Zgodnie z **C2: `immutable`**, stan `closed` jest końcowy. Próba `reopen` zgłoszenia zamkniętego, również jeden dzień po zamknięciu, zwraca `409 Conflict`. Po zamknięciu żadna operacja zmiany stanu nie modyfikuje zgłoszenia ani jego historycznych znaczników czasu; odczyt i filtrowanie pozostają dostępne.

## 6. SLA

Godziny biznesowe to poniedziałek–piątek, półotwarte okno `[08:00:00, 16:00:00)` w strefie `Europe/Warsaw`. Święta publiczne liczą się jak zwykłe dni robocze. Czas poza tym oknem nie zużywa SLA opartego na czasie biznesowym. Początek obliczeń przypadający przed otwarciem jest przesuwany na 08:00 tego samego dnia roboczego, a przypadający po zamknięciu lub w weekend — na 08:00 następnego dnia roboczego. Czas jest następnie konsumowany w kolejnych oknach. Termin wypadający dokładnie o 16:00 pozostaje o 16:00 tego dnia, a nie przechodzi na 08:00 dnia następnego. Obliczenia są świadome zmian CET/CEST według bazy IANA dla `Europe/Warsaw`, a wynik jest zwracany w UTC z `Z`.

Cele SLA wynoszą:

| Priorytet | Potwierdzenie | Rozwiązanie | Rodzaj zegara |
|---|---:|---:|---|
| P1 | 15 minut | 4 godziny | czas kalendarzowy (`wallclock`) |
| P2 | 1 godzina biznesowa | 8 godzin biznesowych | czas biznesowy |
| P3 | 4 godziny biznesowe | 24 godziny biznesowe | czas biznesowy |
| P4 | 8 godzin biznesowych | 72 godziny biznesowe | czas biznesowy |

Zgodnie z **C1: `wallclock`**, P1 biegnie bez przerw przez całą dobę, także wieczorem i w weekend. Dla utworzenia P1 w piątek 2026-10-16 o 15:00:00Z terminy to odpowiednio `2026-10-16T15:15:00Z` i `2026-10-16T19:00:00Z`.

Dokładne wyniki opublikowanych wektorów dla wybranych zegarów są następujące:

| Wektor | Priorytet i `created_at` | `ack_due_at` | `resolve_due_at` |
|---|---|---|---|
| T1 | P1, `2026-10-14T10:00:00Z` | `2026-10-14T10:15:00Z` | `2026-10-14T14:00:00Z` |
| T2 | P3, `2026-10-16T13:30:00Z` | `2026-10-19T09:30:00Z` | `2026-10-21T13:30:00Z` |
| T3 | P1, `2026-10-16T15:00:00Z` | `2026-10-16T15:15:00Z` | `2026-10-16T19:00:00Z` |
| T4 | P2, `2026-10-17T10:00:00Z` | `2026-10-19T07:00:00Z` | `2026-10-19T14:00:00Z` |
| T5 | P4, `2027-01-14T14:30:00Z` | `2027-01-15T14:30:00Z` | `2027-01-27T14:30:00Z` |
| T6 | P1, `2027-01-15T15:50:00Z` | `2027-01-15T16:05:00Z` | `2027-01-15T19:50:00Z` |
| T7 | P2, `2026-10-14T10:00:00Z` | `2026-10-14T11:00:00Z` | `2026-10-15T10:00:00Z` |
| T8 | P3, `2026-10-23T13:00:00Z` | `2026-10-26T10:00:00Z` | `2026-10-28T14:00:00Z` |

`ack_breached` jest `true`, jeśli `acknowledged_at` jest nieustawione i `now > ack_due_at` albo jeśli jest ustawione i `acknowledged_at > ack_due_at`. Potwierdzenie wykonane po terminie pozostaje więc przekroczeniem; wykonane przed terminem lub dokładnie w terminie nim nie jest.

`resolve_breached` jest `true`, jeśli `resolved_at` jest nieustawione i `now > resolve_due_at` albo jeśli jest ustawione i `resolved_at > resolve_due_at`. Rozwiązanie wykonane po terminie pozostaje przekroczeniem, a równość nie jest przekroczeniem. Po `reopen` wyczyszczone `resolved_at` oznacza, że zgłoszenie ponownie jest traktowane jako nierozwiązane i oceniane względem niezmienionego, pierwotnego `resolve_due_at`.

`paused` może być `true` wyłącznie wtedy, gdy zgłoszenie nie jest w stanie `resolved` ani `closed`, jego cel rozwiązania korzysta z zegara biznesowego i `now` wypada poza oknem biznesowym. Jest `false` w aktywnym oknie, dla zakończonego zgłoszenia oraz zawsze dla P1 korzystającego zgodnie z C1 z zegara kalendarzowego.

## 7. Zegar testowy `X-Test-Clock`

Jeśli zmienna środowiskowa `SVCDESK_TEST_CLOCK` ma wartość `"1"` albo `"true"`, każde żądanie może przekazać nagłówek `X-Test-Clock` z chwilą RFC 3339 zawierającą offset (zalecane `Z`; timestamp bez strefy jest nieprawidłowy). Wtedy ta chwila jest wyłącznym „teraz” dla danego żądania: ustala `created_at`, `acknowledged_at`, `resolved_at` i `closed_at`, służy do wyliczenia terminów przy tworzeniu oraz do oceny przekroczeń, pauzy i okna `reopen`. Zegar jest per request, a kolejne żądania mogą celowo używać wcześniejszych lub późniejszych chwil; usługa nie porównuje zegarów kolejnych requestów, nie wymaga monotoniczności i nie odrzuca akcji tylko dlatego, że jej zegar jest wcześniejszy od zapisanego timestampu.

Przy włączonej funkcji niepoprawna wartość, w tym `X-Test-Clock: yesterday`, zwraca `400 Bad Request` albo `422 Unprocessable Entity` i nie wykonuje operacji. Bez nagłówka używany jest rzeczywisty czas UTC. Gdy zmienna jest nieustawiona albo ma wartość `"0"`, nagłówek jest ignorowany i używany jest rzeczywisty czas UTC. Dla `GET /tickets` i `GET /tickets/{id}` nagłówek nie ma znaczenia, ponieważ odpowiedzi tych endpointów nie zawierają pól zależnych od bieżącego czasu. Nagłówek wpływa wyłącznie na czas, nie omija walidacji ani reguł przejść.

## 8. Persystencja i uruchomienie przez Docker Compose

Dane zgłoszeń muszą być trwałe przy ponownym uruchomieniu lub odtworzeniu kontenera i przechowywane pod `/data` na nazwanym wolumenie `svcdesk-data`; nie wolno używać bind mountów ścieżek hosta. Zapisy zmiany stanu i znaczników czasu muszą być spójne, aby po restarcie nie pojawił się częściowo wykonany transition ani ponownie użyty identyfikator.

Plik Compose definiuje usługę dokładnie `svcdesk` z `build:`, nasłuchującą wewnątrz kontenera na porcie 8080 i otrzymującą `SVCDESK_TEST_CLOCK: "1"`. Obraz instaluje zależności podczas budowania i po zbudowaniu uruchamia się bez dostępu do sieci. `docker compose up --wait svcdesk` ma zakończyć się w ciągu 120 sekund, a `/health` ma w tym samym limicie potwierdzić gotowość kodem 200. Konfiguracja żadnej usługi nie może zawierać host-path bind mount ani wolumenu emulującego bind przez `driver_opts`.
