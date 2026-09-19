<!-- ai-generated: 100% - AI drafted the specification from the published course requirements and checks. -->
# Specyfikacja usługi `svcdesk` — Laboratory 1

## 1. Cel i zakres

`svcdesk` jest pojedynczą usługą HTTP/JSON do rejestrowania i obsługi zgłoszeń service desk. Usługa nadaje zgłoszeniom priorytet na podstawie wpływu i pilności, pilnuje ich cyklu życia oraz oblicza terminy SLA. Wszystkie znaczniki czasu w API są reprezentowane jako poprawne daty i czasy RFC 3339 z informacją o strefie; porównania dotyczą tej samej chwili niezależnie od zapisanego offsetu.

Niniejsza specyfikacja jawnie przyjmuje rozstrzygnięcia konfliktów: **C1: `wallclock`**, **C2: `immutable`**, **C3: `matrix`**.

## 2. Reprezentacja zgłoszenia

Zgłoszenie zwracane przez API zawiera co najmniej:

- `id`: niepusty, unikatowy napis nadany przez usługę;
- `title`: tytuł przekazany przy tworzeniu;
- `impact` i `urgency`: liczby całkowite od 1 do 3;
- `reporter`: obiekt zawierający co najmniej niepuste pole `name` oraz opcjonalne logiczne `vip`;
- `priority`: jedna z wartości `P1`, `P2`, `P3`, `P4`, wyliczona przez usługę;
- `state`: `new`, `acknowledged`, `in_progress`, `resolved` albo `closed`;
- `created_at` oraz, gdy dana czynność już nastąpiła, odpowiednio `acknowledged_at`, `resolved_at` i `closed_at`;
- `sla`: obiekt zawierający co najmniej `ack_due_at` i `resolve_due_at`.

Pola czasu dotyczące czynności nie mogą być ustawione przed wykonaniem tych czynności. Odpowiedzi błędów są JSON-em z polem najwyższego poziomu `error`, opisującym błąd w sposób czytelny dla klienta.

## 3. Endpointy

### `GET /health`

Zwraca `200 OK` i JSON `{ "status": "ok" }`, gdy proces jest gotowy do obsługi żądań. Nieistniejąca trasa zwraca `404 Not Found`.

### `POST /tickets`

Tworzy zgłoszenie. Wymagany JSON zawiera `title`, `impact`, `urgency` oraz `reporter` z polem `name`; `reporter.vip` jest opcjonalną wartością logiczną. `title` ma od 1 do 200 znaków. `impact` i `urgency` muszą być liczbami całkowitymi należącymi do zbioru `{1, 2, 3}`. Pole `priority` przesłane przez klienta jest ignorowane: jedynym źródłem priorytetu jest macierz z rozdziału 4.

Sukces zwraca `201 Created` i kompletne zgłoszenie w stanie `new`, z nowym identyfikatorem, `created_at`, wyliczonym `priority` oraz oboma terminami SLA. Brak wymaganego pola, tytuł dłuższy niż 200 znaków, `impact` poza zakresem (w szczególności `5`), tekstowa pilność (w szczególności `"high"`), nieprawidłowy typ lub niepoprawny JSON zwracają `400 Bad Request` albo `422 Unprocessable Entity`, z JSON-em zawierającym `error`.

### `GET /tickets/{id}`

Zwraca `200 OK` i zgłoszenie o podanym identyfikatorze. Nieznany identyfikator zwraca `404 Not Found` z polem `error`.

### `GET /tickets`

Zwraca `200 OK` i tablicę zgłoszeń. Opcjonalne parametry `state` i `priority` filtrują wynik odpowiednio po dokładnej wartości stanu i priorytetu. Po podaniu filtra tablica nie może zawierać zgłoszeń niespełniających filtra; brak wyników oznacza pustą tablicę.

### Operacje zmiany stanu

- `POST /tickets/{id}/ack`: dozwolone wyłącznie dla `new`; zwraca `200 OK`, stan `acknowledged` i ustawia `acknowledged_at` na bieżący czas żądania.
- `POST /tickets/{id}/start`: dozwolone wyłącznie dla `acknowledged`; zwraca `200 OK` i stan `in_progress`.
- `POST /tickets/{id}/resolve`: dozwolone wyłącznie dla `in_progress`; zwraca `200 OK`, stan `resolved` i ustawia `resolved_at` na bieżący czas żądania.
- `POST /tickets/{id}/close`: dozwolone wyłącznie dla `resolved`; zwraca `200 OK`, stan `closed` i ustawia `closed_at` na bieżący czas żądania.
- `POST /tickets/{id}/reopen`: dla `resolved` jest dozwolone nie później niż 7 dni od `resolved_at` i zwraca `200 OK` ze stanem `in_progress`; po upływie 7 dni zwraca `409 Conflict`.

Operacja wykonana ze stanu, z którego nie ma odpowiadającego przejścia, zwraca `409 Conflict` i nie zmienia zgłoszenia. Dotyczy to między innymi: ponownego potwierdzenia, rozpoczęcia `new`, rozwiązania `new` lub `acknowledged`, zamknięcia `new` i ponownego otwarcia `new`.

### `GET /tickets/{id}/sla`

Zwraca `200 OK` i bieżący stan SLA zgłoszenia, obejmujący co najmniej logiczne pola `ack_breached`, `resolve_breached` i `paused` oraz terminy `ack_due_at` i `resolve_due_at`. Nieznane zgłoszenie zwraca `404 Not Found` z polem `error`.

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

Jedyną drogą wstecz jest `resolved -> in_progress` przez `reopen`, o ile od `resolved_at` nie upłynęło więcej niż 7 dni. Przykładowo ponowne otwarcie po 6 dniach jest dozwolone, a po 7 dniach i 1 sekundzie nie jest.

Zgodnie z **C2: `immutable`**, stan `closed` jest końcowy. Próba `reopen` zgłoszenia zamkniętego, również jeden dzień po zamknięciu, zwraca `409 Conflict`. Po zamknięciu żadna operacja zmiany stanu nie modyfikuje zgłoszenia ani jego historycznych znaczników czasu; odczyt i filtrowanie pozostają dostępne.

## 6. SLA

Godziny biznesowe to poniedziałek–piątek, 08:00–16:00 w strefie `Europe/Warsaw`. Czas poza tym oknem nie zużywa SLA opartego na czasie biznesowym. Start poza godzinami biznesowymi jest przesuwany do początku następnego okna; termin wypadający dokładnie o 16:00 jest prawidłowy. Zmiana CET/CEST musi wynikać z reguł strefy `Europe/Warsaw`, a odpowiedzi mogą być normalizowane do UTC.

Cele SLA wynoszą:

| Priorytet | Potwierdzenie | Rozwiązanie | Rodzaj zegara |
|---|---:|---:|---|
| P1 | 15 minut | 4 godziny | czas kalendarzowy (`wallclock`) |
| P2 | 1 godzina biznesowa | 8 godzin biznesowych | czas biznesowy |
| P3 | 4 godziny biznesowe | 24 godziny biznesowe | czas biznesowy |
| P4 | 8 godzin biznesowych | 80 godzin biznesowych | czas biznesowy |

Zgodnie z **C1: `wallclock`**, P1 biegnie bez przerw przez całą dobę, także wieczorem i w weekend. Dla utworzenia P1 w piątek 2026-10-16 o 15:00:00Z terminy to odpowiednio `2026-10-16T15:15:00Z` i `2026-10-16T19:00:00Z`.

`ack_breached` staje się `true`, gdy bieżący czas przekroczył `ack_due_at`, o ile zgłoszenie nie zostało wcześniej potwierdzone. Potwierdzenie przed terminem utrwala brak przekroczenia SLA potwierdzenia także przy późniejszych odczytach. `resolve_breached` analogicznie sygnalizuje przekroczenie `resolve_due_at`, jeżeli rozwiązanie nie nastąpiło na czas. Dla SLA biznesowego `paused` ma wartość `true` poza godzinami biznesowymi (np. w sobotę), a `false` w aktywnym oknie (np. w poniedziałek o 09:00 czasu lokalnego). Dla P1 zegar kalendarzowy nie jest pauzowany.

## 7. Zegar testowy `X-Test-Clock`

Jeśli zmienna środowiskowa `SVCDESK_TEST_CLOCK` ma wartość `"1"`, każde żądanie może przekazać nagłówek `X-Test-Clock` z datą i czasem RFC 3339. Wtedy ta chwila jest wyłącznym „teraz” dla danego żądania: ustala znaczniki czasu operacji, służy do wyliczenia terminów przy tworzeniu oraz do oceny SLA i dozwolonego okna `reopen`. Zegar jest per request, a kolejne żądania mogą celowo używać wcześniejszych lub późniejszych chwil; usługa nie wymaga globalnej monotoniczności nagłówka.

Przy włączonej funkcji niepoprawna wartość, w tym `X-Test-Clock: yesterday`, zwraca `400 Bad Request` albo `422 Unprocessable Entity` i nie wykonuje operacji. Bez nagłówka używany jest rzeczywisty czas systemowy. Gdy `SVCDESK_TEST_CLOCK` nie ma wartości `"1"`, klient nie może sterować czasem nagłówkiem i usługa korzysta z czasu systemowego. Nagłówek wpływa wyłącznie na czas, nie omija walidacji ani reguł przejść.

## 8. Persystencja i uruchomienie przez Docker Compose

Dane zgłoszeń muszą być trwałe przy ponownym uruchomieniu lub odtworzeniu kontenera i przechowywane pod `/data` na nazwanym wolumenie `svcdesk-data`; nie wolno używać bind mountów ścieżek hosta. Zapisy zmiany stanu i znaczników czasu muszą być spójne, aby po restarcie nie pojawił się częściowo wykonany transition ani ponownie użyty identyfikator.

Plik Compose definiuje usługę dokładnie `svcdesk` z `build:`, nasłuchującą wewnątrz kontenera na porcie 8080 i otrzymującą `SVCDESK_TEST_CLOCK: "1"`. Obraz instaluje zależności podczas budowania i po zbudowaniu uruchamia się bez dostępu do sieci. `docker compose up --wait svcdesk` ma zakończyć się w ciągu 120 sekund, a `/health` ma w tym samym limicie potwierdzić gotowość kodem 200. Konfiguracja żadnej usługi nie może zawierać host-path bind mount ani wolumenu emulującego bind przez `driver_opts`.
