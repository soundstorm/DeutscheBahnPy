# DeutscheBahnPy
Python-Schnittstelle für Kommunikation mit der Deutschen Bahn.

Nutzt die inoffizielle JSON-API der DB Navigator App (`app.services-bahn.de/mob/`).
Die alten XML-Endpunkte unter `reiseauskunft.bahn.de` existieren nicht mehr.
Die API steht hinter einem TLS-Proxy, der Clients anhand des TLS-Fingerprints
filtert; `deutschebahn.py` setzt deshalb dieselben Cipher-Suites wie die App.

Reines Standard-Library-Modul, keine externen Abhängigkeiten. Python 3.7+.

## Nutzung

```python
import deutschebahn as db

station = db.station_by_name("Hannover Hbf")
for journey in db.station_board(station["locationId"], "departure")[:10]:
    print(f"{journey['time']:%H:%M}\t{journey['productShort']} {journey['line']}\t{journey['direction']}")
```

### Stationssuche

```python
db.find_stations("Nordstadt")          # rohe Trefferliste (Stationen/Adressen/POIs)
db.station_by_name("Hannover Hbf")     # erster Stations-Treffer
db.station_details(eva_nr)             # Details/verfügbare Produkte einer Station
```

### Abfahrts-/Ankunftstafel

```python
db.station_board(location_id, board_type="departure")  # oder "arrival"
```

Optional: `products` (Iterable aus `db.PRODUCTS.values()`, Standard: alle) zum
Filtern nach Verkehrsmitteln, `when` (datetime, Standard: jetzt).

Jeder Eintrag ist ein dict mit `time`, `realTime`, `delay` (Minuten),
`platform`, `newPlatform`, `direction`, `product`, `productShort`, `line`,
`cancelled` und `notes`.

## Hinweise

- Diese Bibliothek nutzt eine nicht offiziell dokumentierte, reverse-engineerte
  Schnittstelle der DB Navigator App. Sie kann sich jederzeit ohne Vorankündigung
  ändern. Nur für private, nicht-kommerzielle Zwecke.
- Eine Verbindungssuche (Fahrplanauskunft zwischen zwei Stationen) ist aktuell
  nicht implementiert.
- Portiert von / orientiert an [dbapi_php](https://github.com/soundstorm/dbapi_php).
