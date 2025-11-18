# CalBench
Projekt z przedmiotu Sieci Komputerowe - Projektowanie i Budowa (CalBench)

**CalBench** to aplikacja desktopowa służąca do symulacji uproszczonego działania sieci Ethernet, opartej na mechanizmie dostępu do medium **CSMA/CD** (Carrier Sense Multiple Access with Collision Detection).

Projekt składa się z dwóch głównych części:
1.  **Interfejsu Graficznego (GUI)**, który pozwala użytkownikowi na interaktywne zadawanie parametrów symulacji i obserwację wyników.
2.  **Symulacji**, która w tle wykonuje obliczenia, modelując zachowanie węzłów sieciowych, transmisję danych oraz występowanie kolizji.

Głównym celem aplikacji jest umożliwienie analizy wydajności sieci (np. realnej przepustowości) w zależności od zadanego obciążenia, liczby urządzeń i przepustowości medium.

## 1. Architektura Aplikacji

### Interfejs Graficzny (GUI)

Interfejs został stworzony przy użyciu bibliotek `tkinter` oraz `ttkbootstrap`, co nadaje mu nowoczesny wygląd. Działanie GUI jest oddzielone od logiki symulacji dzięki wykorzystaniu **wielowątkowości**.

- **Panel konfiguracyjny (lewa strona):**
  Użytkownik może zdefiniować kluczowe parametry symulacji:
  - **Czas przesyłu danych [s]:** Jak długo ma trwać symulacja.
  - **Ilość węzłów:** Liczba urządzeń podłączonych do sieci.
  - **Przepustowość sieci [Mb/s]:** Maksymalna prędkość medium transmisyjnego.
  - **Obciążenie sieci [Mb/s]:** Sumaryczna ilość danych, jaką wszystkie węzły próbują wysłać w ciągu sekundy.

- **Panel wyników (prawa strona):**
  - **Wskaźnik postępu (`Meter`):** Na bieżąco pokazuje całkowitą ilość przesłanych danych w Megabajtach.
  - **Statystyki końcowe:** Po zakończeniu symulacji wyświetlane są kluczowe metryki wydajności, takie jak realna przepustowość, procentowy udział przesłanych danych, liczba kolizji i liczba porzuconych ramek.

Gdy użytkownik klika "Start", symulacja uruchamiana jest w osobnym wątku. Komunikacja między wątkiem symulacyjnym a głównym wątkiem GUI odbywa się za pomocą kolejki (`queue.Queue`), co zapobiega blokowaniu interfejsu i pozwala na płynne odświeżanie wyników.

### Silnik Symulacyjny

Rdzeń aplikacji to **symulator zdarzeniowy**, który modeluje procesy zachodzące w sieci w dyskretnych krokach czasowych.

- **Główne klasy modelu:**
  - `Simulator`: Centralny obiekt zarządzający całą symulacją. Przetwarza kolejkę zdarzeń, zarządza upływem czasu i koordynuje działanie pozostałych komponentów.
  - `Node`: Reprezentuje pojedyncze urządzenie (stację roboczą) w sieci. Każdy węzeł generuje ramki danych i próbuje je wysłać zgodnie z zasadami CSMA/CD:
    1. Nasłuchuje, czy medium jest wolne.
    2. Jeśli tak, rozpoczyna transmisję.
    3. Jeśli dojdzie do kolizji, przerywa nadawanie i uruchamia algorytm **Binary Exponential Backoff**, aby odczekać losowy czas przed kolejną próbą.
  - `Frame`: Prosta struktura reprezentująca pojedynczą ramkę danych do przesłania.
  - `Medium`: Modeluje współdzielone medium transmisyjne (np. kabel Ethernet). Sprawdza, czy jest zajęte i oblicza czas potrzebny na transmisję ramki.
  - `Stats`: Obiekt zbierający statystyki w trakcie trwania symulacji (np. zlicza kolizje, odebrane bajty, opóźnienia), które są następnie prezentowane jako wynik końcowy.
  - `Event`: Reprezentuje pojedyncze zdarzenie w symulacji (np. "wygeneruj nową ramkę", "zakończ transmisję", "spróbuj wysłać dane"), które ma przypisany dokładny czas wystąpienia.

## 3. Przebieg Symulacji

1.  Po uruchomieniu, na podstawie parametrów wejściowych, tworzone są początkowe zdarzenia generowania ramek dla każdego z węzłów.
2.  Główna pętla symulatora pobiera z kolejki zdarzenie o najwcześniejszym czasie wystąpienia.
3.  Czas symulacji jest przesuwany do czasu tego zdarzenia.
4.  Wykonywana jest akcja powiązana ze zdarzeniem (np. próba transmisji, obsługa kolizji).
5.  W wyniku tej akcji do kolejki mogą zostać dodane nowe, przyszłe zdarzenia (np. zdarzenie końca transmisji lub kolejna próba wysłania po kolizji).
6.  Proces jest powtarzany do momentu osiągnięcia zadanego czasu symulacji.
7.  Na końcu generowany jest raport końcowy na podstawie zebranych statystyk.
