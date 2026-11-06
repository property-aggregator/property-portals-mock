# property-portals-mock

Symulowane portale ogłoszeniowe (OLX i Otodom) do testów scrapera. Zwracają strony w tym samym formacie, którego oczekuje `OlxScraper` i `OtodomScraper`, a dane są w całości syntetyczne (bez prawdziwych ogłoszeń i bez danych osobowych sprzedających).

## Uruchomienie

Wymagany jest Python 3.11+. Mock używa wyłącznie biblioteki standardowej.

```
python -m server --port 8080 --scenario normal
```

Sprawdzenie: `http://127.0.0.1:8080/health` zwraca `ok`.

Testy mocka (wymagają `pytest`):

```
pip install pytest
python -m pytest -q tests
```

Test zgodności z prawdziwymi parserami scrapera uruchamia się, gdy wskażesz katalog `scraper/src`:

```
SCRAPER_SRC=../scraper/src python -m pytest -q tests
```

## Endpointy

| Ścieżka | Portal | Co zwraca |
|---|---|---|
| `/nieruchomosci/mieszkania/sprzedaz/{województwo}/` | OLX | karty `data-testid="l-card"`, stan `__PRERENDERED_STATE__=`, 40 ofert na stronę, max 25 stron, `totalElements` ucinane do 1000 |
| `/pl/wyniki/sprzedaz/mieszkanie,rynek-wtorny/cala-polska` | Otodom | `__NEXT_DATA__` z `searchAds`, `limit` do 72, po ostatniej stronie zwraca stronę 1 |
| `/health` | - | `ok` |

Parametry filtrów OLX (`search[filter_float_price:from]` i `:to`) działają jak w prawdziwym portalu, więc dzielenie województwa na przedziały cen działa tak samo.

Około 8% ogłoszeń na OLX linkuje do Otodomu. Scraper je pomija, tak jak w prawdziwym portalu.

## Scenariusze

Scenariusz wybierasz przy starcie (`--scenario`). Każdy celowo psuje jedną rzecz:

| Scenariusz | Co się dzieje |
|---|---|
| `normal` | prawidłowe odpowiedzi |
| `empty` | brak ofert na każdej stronie |
| `layout_change` | HTML bez atrybutów `data-testid` (OLX) i bez `__NEXT_DATA__` (Otodom) |
| `no_state` | OLX bez stanu `__PRERENDERED_STATE__` |
| `rate_limit` | co trzecie żądanie dostaje 429 z `Retry-After` |
| `server_error` | strona 2 każdego listingu zwraca 500 |

## Wyniki scrapera na mocku (zmierzone)

Tabela pokazuje, co `FullScrape` zwrócił na tym mocku przy stanie repo `main` (commit `0346042`). To są oczekiwane wartości referencyjne dla testów scrapera.

| Scenariusz | OLX: oferty / completed | Otodom: oferty / completed |
|---|---|---|
| normal | 2002 / True | 2570 / True |
| empty | 0 / True | 0 / False |
| layout_change | 0 / **True** | 0 / False |
| no_state | 2002 / True | 2570 / True |
| rate_limit | 2002 / True | 2570 / True |
| server_error | 234 / False | 72 / False |

Dwa przypadki wymagają uwagi:

- **layout_change na OLX** zwraca 0 ofert, ale `completed=True`. To cicha awaria: scraper nie zgłasza problemu.
- **no_state** daje identyczny wynik jak normal, bo OLX nie czyta stanu `__PRERENDERED_STATE__`. Przyczyna: w `_prerendered_listing` wynik `json.JSONDecoder().raw_decode` (już słownik) jest przekazywany do `json.loads`, który rzuca `TypeError`. Błąd jest po cichu łapany i scraper loguje „Could not read OLX prerendered state”. W efekcie dla OLX zawsze brakuje `province` i `seller_type`.

## Co mock nie robi

- Scraper ma adresy `BASE_URL` wpisane na sztywno (`https://www.olx.pl`, `https://www.otodom.pl`). Żeby scraper korzystał z mocka, potrzebna jest konfiguracja adresu bazowego w scraperze. Ta zmiana należy do scrapera i nie jest zrobiona w tym repo.
- Mock nie imituje zabezpieczeń (TLS fingerprinting, Cloudflare), więc scraper zawsze dostaje odpowiedź bez 403.
- Obrazy są adresami `img.portal-mock.test` i nie są serwowane.

## Dane

Dane są generowane z ustalonego ziarna (`server/data.py`). Każde uruchomienie zwraca te same oferty. Liczby ofert na województwo ustawiasz w słowniku `REGIONS`.
