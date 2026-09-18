#!/usr/bin/env python3
"""Unofficial Python client for the Deutsche Bahn "DB Navigator" mobile API.

The old public XML endpoints under reiseauskunft.bahn.de have been shut
down. The DB Navigator app now talks to a JSON API under
app.services-bahn.de/mob/, fronted by a TLS proxy that rejects clients
whose TLS ClientHello doesn't look like the app's. This client mirrors the
endpoints, headers and cipher suites of the reverse-engineered PHP client
at https://github.com/soundstorm/dbapi_php.

This is unofficial, reverse-engineered, and may break without notice --
use for personal, non-commercial purposes only.
"""

import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime

BASE_URL = "https://app.services-bahn.de/mob"
USER_AGENT = "DBNavigator/iOS/26.12.1"
CORRELATION_ID = "FOO"
DEFAULT_TIMEOUT = 15

# The API's TLS proxy fingerprints clients and rejects OpenSSL's default
# cipher list; these are the suites the official app negotiates.
TLS_CIPHERS = (
    "ECDHE-ECDSA-AES128-GCM-SHA256:"
    "ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-CHACHA20-POLY1305"
)
# TLS 1.3 suite selection has no public API in Python's ssl module; OpenSSL's
# default order (AES-128-GCM, AES-256-GCM, ChaCha20-Poly1305) already
# matches the app's --tls13-ciphers list, so nothing to restrict there.

MEDIA_TYPE_LOCATION = "application/x.db.vendo.mob.location.v3+json"
MEDIA_TYPE_BAHNHOFSTAFEL = "application/x.db.vendo.mob.bahnhofstafeln.v2+json"

# Transport-type filters accepted by the bahnhofstafel (station board) endpoint.
PRODUCTS = {
    "ice": "HOCHGESCHWINDIGKEITSZUEGE",
    "ic_ec": "INTERCITYUNDEUROCITYZUEGE",
    "ir": "INTERREGIOUNDSCHNELLZUEGE",
    "re": "NAHVERKEHRSONSTIGEZUEGE",
    "s": "SBAHNEN",
    "bus": "BUSSE",
    "ship": "SCHIFFE",
    "u": "UBAHN",
    "tram": "STRASSENBAHN",
    "ast": "ANRUFPFLICHTIGEVERKEHRE",
}
ALL_PRODUCTS = tuple(PRODUCTS.values())


class DeutscheBahnError(Exception):
    """Raised when the Deutsche Bahn API can't be reached or returns bad data."""


def _ssl_context():
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers(TLS_CIPHERS)
    return context


_CONTEXT = _ssl_context()


def _request(path, body=None, media_type=None, timeout=DEFAULT_TIMEOUT):
    headers = {
        "User-Agent": USER_AGENT,
        "X-Correlation-ID": CORRELATION_ID,
    }
    if media_type:
        headers["Accept"] = media_type

    data = None
    method = "GET"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = media_type
        method = "POST"

    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CONTEXT) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return json.loads(resp.read().decode(charset))
    except (urllib.error.URLError, ssl.SSLError, TimeoutError) as exc:
        raise DeutscheBahnError(f"request to {path} failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DeutscheBahnError(f"invalid JSON response from {path}: {exc}") from exc


def find_stations(search_term, location_types=("ST",), timeout=DEFAULT_TIMEOUT):
    """Search for stations (or addresses/POIs) by name.

    Returns the raw list of location dicts from the API, each containing at
    least "name" and "locationId", and for stations "evaNr"/"stationId".
    """
    body = {"searchTerm": search_term, "locationTypes": list(location_types)}
    return _request("/location/search", body=body, media_type=MEDIA_TYPE_LOCATION, timeout=timeout)


def station_by_name(name, timeout=DEFAULT_TIMEOUT):
    """Return the first station matching ``name``, or ``None``."""
    for location in find_stations(name, location_types=("ST",), timeout=timeout):
        if location.get("locationType") == "ST":
            return location
    return None


def station_details(eva_nr, timeout=DEFAULT_TIMEOUT):
    """Fetch details (available products etc.) for a station by its EVA number."""
    return _request(f"/location/details/{eva_nr}", media_type=MEDIA_TYPE_LOCATION, timeout=timeout)


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")


def _parse_journey(entry, board_type):
    if board_type == "arrival":
        scheduled = _parse_time(entry.get("ankunftsDatum"))
        real = _parse_time(entry.get("ezAnkunftsDatum")) or scheduled
        direction = entry.get("abgangsOrt", "-")
    else:
        scheduled = _parse_time(entry.get("abgangsDatum"))
        real = _parse_time(entry.get("ezAbgangsDatum")) or scheduled
        direction = entry.get("richtung", "-")

    delay_minutes = None
    if scheduled and real:
        delay_minutes = int((real - scheduled).total_seconds() // 60)

    line = entry.get("mitteltext", "") or ""
    product_short, _, line_number = line.partition(" ")
    notes = entry.get("echtzeitNotizen", []) or []

    return {
        "time": scheduled,
        "realTime": real,
        "delay": delay_minutes,
        "platform": entry.get("gleis", "-"),
        "newPlatform": entry.get("ezGleis"),
        "direction": direction,
        "product": entry.get("produktGattung"),
        "productShort": product_short,
        "line": line_number,
        "cancelled": any(note.get("text") == "Halt entfällt" for note in notes),
        "notes": notes,
    }


def station_board(location_id, board_type="departure", products=ALL_PRODUCTS, when=None, timeout=DEFAULT_TIMEOUT):
    """Fetch the departure or arrival board for a station.

    :param location_id: the "locationId" of the station (from find_stations()).
    :param board_type: "departure" or "arrival".
    :param products: iterable of product filter constants, see PRODUCTS.
    :param when: datetime to query, defaults to now.
    """
    if board_type not in ("departure", "arrival"):
        raise ValueError("board_type must be 'departure' or 'arrival'")

    endpoint = "abfahrt" if board_type == "departure" else "ankunft"
    when = when or datetime.now()
    body = {
        "datum": when.strftime("%Y-%m-%d"),
        "anfragezeit": when.strftime("%H:%M"),
        "ursprungsBahnhofId": location_id,
        "verkehrsmittel": list(products),
    }
    result = _request(f"/bahnhofstafel/{endpoint}", body=body, media_type=MEDIA_TYPE_BAHNHOFSTAFEL, timeout=timeout)

    key = "bahnhofstafelAnkunftPositionen" if board_type == "arrival" else "bahnhofstafelAbfahrtPositionen"
    return [_parse_journey(entry, board_type) for entry in result.get(key, [])]


if __name__ == "__main__":
    station = station_by_name("Hannover Hbf")
    for journey in station_board(station["locationId"], "departure")[:10]:
        print(f"{journey['time']:%H:%M}\t{journey['productShort']} {journey['line']}\t{journey['direction']}")
