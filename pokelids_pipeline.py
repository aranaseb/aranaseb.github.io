#!/usr/bin/env python3
"""
pokelids_pipeline.py
════════════════════
Scrapes local.pokemon.jp for new Pokélids and classifies them.

Steps (run only when new lids are found):
  1. Scrape  — fetch new IDs, download images, append to pokelids.json
  2. Station — nearest train station (id + distance)
  3. Name JA — Japanese place name from the localacts prefecture page
  4. Classify — station_type, nearest roadside station, nearest city

Classification rules:
  roadside     — nearest roadside station ≤ 0.5 km  (overrides all)
  super_remote — nearest train station   > 25 km
  remote       — nearest train station   > 2 km
  walkable     — nearest train station   > 0.5 km
  major        — nearest train station   ≤ 0.5 km, nearest city ≤ 10 km
  local        — nearest train station   ≤ 0.5 km, nearest city > 10 km

Usage:
    python3 pokelids_pipeline.py
    python3 pokelids_pipeline.py --max 800
    python3 pokelids_pipeline.py --no-images
    python3 pokelids_pipeline.py --dry-run
"""

import argparse
import json
import math
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL   = "https://local.pokemon.jp"
DETAIL_URL = BASE_URL + "/en/manhole/desc/{id}/?is_modal=1"
HEADERS    = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Referer": "https://local.pokemon.jp/en/manhole/",
}

DEFAULT_POKELIDS = "data/pokelids.json"
DEFAULT_STATIONS = "data/japan_stations.json"
DEFAULT_ROADSIDE = "data/roadside_stations.json"
DEFAULT_CITIES   = "data/jpcities.json"
DEFAULT_OUTPUT   = "data/pokelids.json"
IMAGE_DIR        = "images_official"

SCRAPE_DELAY    = 0.6
MAX_CONSEC_MISS = 20

ROADSIDE_KM     = 0.5
WALKABLE_KM     = 0.5
REMOTE_KM       = 2.0
SUPER_REMOTE_KM = 25.0
MAJOR_CITY_KM   = 10.0

PREFECTURES = [
    "hokkaido", "aomori", "iwate", "miyagi", "akita", "yamagata", "fukushima",
    "ibaraki", "tochigi", "gunma", "saitama", "chiba", "tokyo", "kanagawa",
    "niigata", "toyama", "ishikawa", "fukui", "yamanashi", "nagano", "gifu",
    "shizuoka", "aichi", "mie", "shiga", "kyoto", "osaka", "hyogo", "nara",
    "wakayama", "tottori", "shimane", "okayama", "hiroshima", "yamaguchi",
    "tokushima", "kagawa", "ehime", "kochi", "fukuoka", "saga", "nagasaki",
    "kumamoto", "oita", "miyazaki", "kagoshima", "okinawa",
]

GMAPS_COORDS = re.compile(r"[?&]q=([-\d.]+),([-\d.]+)")

# Max distance (km) to the nearest already-known lid for the coordinate
# fallback to be trusted. Beyond this, prefecture resolution fails loudly.
COORD_FALLBACK_MAX_KM = 50.0


def normalize_prefecture(text):
    """Map scraped prefecture text to a canonical lowercase slug, or None.

    Handles case differences ("Nagasaki" → "nagasaki") and common suffixes
    ("Nagano Prefecture", "fukui-ken", "osaka-fu", "tokyo-to"). Suffixes are
    only stripped when hyphen/space-separated, so "kyoto" is never mangled.
    """
    if not text:
        return None
    slug = text.strip().lower()
    slug = re.sub(r"[\s\-_]+(prefecture|pref\.?|ken|fu|to|do)$", "", slug)
    return slug if slug in PREFECTURES else None


# GSI (Geospatial Information Authority of Japan) reverse geocoder.
# Returns a municipality code (muniCd); its first 2 digits are the JIS
# prefecture code, which maps 1:1 onto PREFECTURES (already in JIS order).
GSI_REVGEO_URL = (
    "https://mreversegeocoder.gsi.go.jp/reverse-geocoder/"
    "LonLatToAddress?lat={lat}&lon={lng}"
)


def gsi_prefecture(lat, lng, session):
    """Authoritative fallback: prefecture from GSI reverse geocoding, or None."""
    try:
        r = session.get(GSI_REVGEO_URL.format(lat=lat, lng=lng), timeout=15)
        r.raise_for_status()
        muni_cd = r.json().get("results", {}).get("muniCd", "")
        code = int(str(muni_cd)[:2])
        if 1 <= code <= 47:
            return PREFECTURES[code - 1]
    except Exception as e:
        print(f"    [WARN] GSI reverse geocode failed for ({lat}, {lng}): {e}")
    return None


def prefecture_from_coords(lat, lng, data):
    """Fallback: prefecture of the nearest already-known lid.

    Uses the existing dataset as a spatial index. Only returns a match
    within COORD_FALLBACK_MAX_KM to avoid cross-border misfiles.
    """
    candidates = [
        (pref, lid["lat"], lid["lng"])
        for pref, lids in data.items() if pref in PREFECTURES
        for lid in lids
        if lid.get("lat") is not None and lid.get("lng") is not None
    ]
    if not candidates:
        return None
    pref, km = nearest(lat, lng, candidates)
    return pref if km <= COORD_FALLBACK_MAX_KM else None


def resolve_prefecture(raw_text, lat, lng, data, lid_id, session):
    """Resolve a canonical prefecture slug for a new lid, or None.

    Order: normalize scraped text → GSI reverse geocode → nearest-known-lid
    offline fallback. Never invents keys: only slugs in PREFECTURES are
    ever returned.
    """
    pref = normalize_prefecture(raw_text)
    if pref:
        if raw_text != pref:
            print(f"  [{lid_id}] Prefecture '{raw_text}' normalized → '{pref}'")
        return pref

    pref = gsi_prefecture(lat, lng, session)
    if pref:
        print(f"  [{lid_id}] Prefecture unresolved from page "
              f"('{raw_text}') — resolved via GSI reverse geocode → '{pref}'")
        return pref

    pref = prefecture_from_coords(lat, lng, data)
    if pref:
        print(f"  [{lid_id}] Prefecture unresolved from page "
              f"('{raw_text}') — resolved from nearest known lid → '{pref}'")
        return pref
    return None


# ── Geometry ───────────────────────────────────────────────────────────────────

def haversine_km(lat1, lng1, lat2, lng2):
    R    = 6_371.0
    p1   = math.radians(lat1)
    p2   = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a    = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest(lat, lng, candidates):
    """Return (id, distance_km) of the closest candidate in [(id, lat, lng), ...]."""
    best_id, best_km = None, float("inf")
    for cid, clat, clng in candidates:
        km = haversine_km(lat, lng, clat, clng)
        if km < best_km:
            best_id, best_km = cid, km
    return best_id, best_km


def decimal_to_dms(lat, lng):
    def fmt(deg, pos, neg):
        d       = abs(deg)
        degrees = int(d)
        minutes = int((d - degrees) * 60)
        seconds = round((d - degrees - minutes / 60) * 3600, 1)
        return f"{degrees}°{minutes}'{seconds}\"{pos if deg >= 0 else neg}"
    return f"{fmt(lat, 'N', 'S')} {fmt(lng, 'E', 'W')}"


# ── Classification ─────────────────────────────────────────────────────────────

def classify(station_km, roadside_km, city_km):
    if roadside_km <= ROADSIDE_KM:    return "roadside"
    if station_km > SUPER_REMOTE_KM: return "super_remote"
    if station_km > REMOTE_KM:       return "remote"
    if station_km > WALKABLE_KM:     return "walkable"
    if city_km <= MAJOR_CITY_KM:     return "major"
    return "local"


# ── Scraper ────────────────────────────────────────────────────────────────────

def new_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def extract_coords(soup):
    for a in soup.find_all("a", href=True):
        m = GMAPS_COORDS.search(a["href"])
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


def extract_prefecture(soup):
    link_btn = soup.find("div", class_="link-btn")
    if link_btn:
        span = link_btn.find("span")
        if span:
            br = span.find("br")
            if br and br.next_sibling:
                text = (
                    br.next_sibling.strip()
                    if isinstance(br.next_sibling, str)
                    else br.next_sibling.get_text(strip=True)
                )
                if text:
                    return text
    for a in soup.find_all("a", href=re.compile(r"/municipality/")):
        m = re.search(r"/municipality/([^/]+)/", a["href"])
        if m:
            return m.group(1)
    return None


def extract_pokemon(soup):
    names = []
    for a in soup.find_all("a", href=re.compile(r"/pokedex/")):
        name = re.sub(r"\s*Pok[eé]dex$", "", a.get_text(strip=True), flags=re.IGNORECASE).strip()
        if name:
            names.append(name)
    return names


def extract_image_url(soup):
    img = soup.find("img", src=re.compile(r"manhole/.*_l\."))
    return urljoin(BASE_URL, img["src"]) if img else None


def download_image(url, prefecture, lid_id, session):
    safe_pref  = (prefecture or "unknown").replace(" ", "_")
    folder     = os.path.join(IMAGE_DIR, safe_pref)
    os.makedirs(folder, exist_ok=True)
    ext        = os.path.splitext(url.split("?")[0])[1] or ".png"
    local_path = os.path.join(folder, f"{lid_id}{ext}")
    if not os.path.exists(local_path):
        try:
            r = session.get(url, timeout=15)
            r.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(r.content)
            time.sleep(0.1)
        except Exception as e:
            print(f"    [WARN] Image download failed: {url} — {e}")
            return None
    return local_path


def fetch_lid(lid_id, session):
    r = session.get(DETAIL_URL.format(id=lid_id), timeout=15)
    if r.status_code == 404:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    h1   = soup.find("h1")
    if not h1:
        return None
    name = h1.get_text(strip=True)
    if not name or name in ("Poké Lids", "Pokémon Local Acts"):
        return None

    lat, lng = extract_coords(soup)
    if lat is None:
        print(f"  [{lid_id}] No coords for '{name}' — skipping")
        return None

    # NOTE: the image is NOT downloaded here. The prefecture must be
    # resolved to a canonical slug first (see step_scrape), so the image
    # lands in the correct lowercase folder and image_local stays valid.
    return {
        "name":       name,
        "lat":        lat,
        "lng":        lng,
        "prefecture": extract_prefecture(soup),  # raw page text; normalized later
        "pokemon":    extract_pokemon(soup),
        "image_url":  extract_image_url(soup),
    }


def known_ids(data):
    return {lid["id"] for lids in data.values() for lid in lids if isinstance(lid.get("id"), int)}


def build_new_lid(lid_id, fetched, image_local):
    lat, lng = fetched["lat"], fetched["lng"]
    return {
        "id":                                   lid_id,
        "name":                                 fetched["name"],
        "lat":                                  lat,
        "lng":                                  lng,
        "dms":                                  decimal_to_dms(lat, lng),
        "pokemon_featured":                     fetched["pokemon"],
        "image_url":                            fetched["image_url"],
        "image_local":                          image_local,
        "active":                               False,
        "name_ja":                              None,
        "nearest_station_id":                   None,
        "nearest_station_distance_km":          None,
        "station_type":                         None,
        "nearest_roadside_station_id":          None,
        "nearest_roadside_station_distance_km": None,
        "nearest_city":                         None,
        "nearest_city_distance_km":             None,
    }


# ── Steps ──────────────────────────────────────────────────────────────────────

def step_scrape(data, max_id, download_images, dry_run):
    print(f"\n{'═' * 56}\n  STEP 1 — Scrape\n{'═' * 56}")

    existing  = known_ids(data)
    session   = new_session()
    new_keys  = []
    consec    = 0
    new_count = 0

    print(f"  Known IDs: {len(existing)}")

    try:
        for lid_id in range(1, max_id + 1):
            if lid_id in existing:
                continue

            time.sleep(SCRAPE_DELAY)
            try:
                fetched = fetch_lid(lid_id, session)
            except requests.RequestException as e:
                print(f"  [{lid_id}] Request error: {e}")
                continue

            if fetched is None:
                consec += 1
                if consec >= MAX_CONSEC_MISS:
                    print(f"  {MAX_CONSEC_MISS} consecutive misses at {lid_id} — stopping.")
                    break
                continue

            consec     = 0
            new_count += 1

            pref = resolve_prefecture(
                fetched["prefecture"], fetched["lat"], fetched["lng"],
                data, lid_id, session
            )
            if pref is None:
                pref = "unknown"
                print(f"  [{lid_id}] *** WARNING: prefecture could not be resolved "
                      f"(page text: '{fetched['prefecture']}') — filed under "
                      f"'unknown'. FIX MANUALLY before deploying. ***")

            print(f"  [{lid_id}] ✦ NEW  '{fetched['name']}' ({pref})  pokemon={fetched['pokemon']}")

            if not dry_run:
                image_local = (
                    download_image(fetched["image_url"], pref, lid_id, session)
                    if download_images and fetched["image_url"] else None
                )
                lid = build_new_lid(lid_id, fetched, image_local)
                data.setdefault(pref, []).append(lid)
                new_keys.append((pref, len(data[pref]) - 1))

    except KeyboardInterrupt:
        print("\n  Interrupted.")

    print(f"\n  {new_count} new lid(s) found.")
    return new_keys


def step_stations(data, new_keys, stations_path, dry_run):
    print(f"\n{'═' * 56}\n  STEP 2 — Nearest train stations\n{'═' * 56}")

    raw      = json.loads(Path(stations_path).read_text(encoding="utf-8"))
    stations = [(sid, s["lat"], s["lng"]) for sid, s in raw.items()
                if s.get("lat") is not None and s.get("lng") is not None]
    print(f"  Valid stations: {len(stations):,} / {len(raw):,}")

    for pref, idx in new_keys:
        lid              = data[pref][idx]
        station_id, km   = nearest(lid["lat"], lid["lng"], stations)
        print(f"  '{lid['name']}' [{pref}] → {station_id}  ({km:.4f} km)")
        if not dry_run:
            lid["nearest_station_id"]          = station_id
            lid["nearest_station_distance_km"] = round(km, 4)


def fetch_ja_names(slug, session):
    url = f"https://local.pokemon.jp/manhole/{slug}.html"
    try:
        r = session.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return []
    soup  = BeautifulSoup(r.text, "html.parser")
    names = []
    for a in soup.select("a.manhole-detail"):
        img     = a.find("img")
        name_ja = a.get_text(strip=True)
        if not name_ja and img:
            alt     = img.get("alt", "")
            name_ja = alt.split("/")[-1] if "/" in alt else alt
        if name_ja:
            names.append(name_ja)
    return names


def step_names_ja(data, new_keys, dry_run):
    print(f"\n{'═' * 56}\n  STEP 3 — Japanese names\n{'═' * 56}")

    affected = {pref for pref, _ in new_keys}
    session  = new_session()

    for slug in PREFECTURES:
        if slug not in affected:
            continue
        lids = data.get(slug, [])
        if not lids:
            continue

        ja_names = fetch_ja_names(slug, session)
        time.sleep(0.75)
        print(f"  '{slug}': {len(ja_names)} JA names / {len(lids)} lids")

        if not ja_names:
            continue
        if len(ja_names) != len(lids):
            print(f"  WARNING: count mismatch — assigning positionally, check manually")

        for i, lid in enumerate(lids):
            if lid.get("name_ja") is not None:
                continue
            name_ja = ja_names[i] if i < len(ja_names) else lid["name"]
            print(f"    '{lid['name']}' → {name_ja}")
            if not dry_run:
                lid["name_ja"] = name_ja


def step_classify(data, new_keys, roadside_path, cities_path, dry_run):
    print(f"\n{'═' * 56}\n  STEP 4 — Classify\n{'═' * 56}")

    roadside_raw = json.loads(Path(roadside_path).read_text(encoding="utf-8"))
    roadside     = [(k, v["lat"], v["lng"]) for k, v in roadside_raw.items()
                    if v.get("lat") is not None and v.get("lng") is not None]
    cities       = [(c["key"], c["lat"], c["lng"])
                    for c in json.loads(Path(cities_path).read_text(encoding="utf-8"))]
    print(f"  Roadside stations: {len(roadside):,}  Cities: {len(cities):,}")

    for pref, idx in new_keys:
        lid        = data[pref][idx]
        station_km = lid.get("nearest_station_distance_km")
        if station_km is None:
            print(f"  SKIP '{lid['name']}' — station distance missing")
            continue

        roadside_id, rs_km = nearest(lid["lat"], lid["lng"], roadside)
        city_id,  city_km  = nearest(lid["lat"], lid["lng"], cities)
        station_type       = classify(station_km, rs_km, city_km)

        print(f"  '{lid['name']}' [{pref}] → {station_type} "
              f"(station={station_km:.3f}km  roadside={rs_km:.3f}km  city={city_km:.3f}km)")

        if not dry_run:
            lid["station_type"]                          = station_type
            lid["nearest_roadside_station_id"]           = roadside_id
            lid["nearest_roadside_station_distance_km"]  = round(rs_km, 4)
            lid["nearest_city"]                          = city_id
            lid["nearest_city_distance_km"]              = round(city_km, 4)


# ── I/O ────────────────────────────────────────────────────────────────────────

def load_data(path):
    if not os.path.exists(path):
        print(f"No file at {path} — starting fresh.")
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for lids in data.values():
        for lid in lids:
            if "active" not in lid:
                lid["active"] = False
    print(f"Loaded {sum(len(v) for v in data.values())} lids from {path}")
    return data


def save_data(data, path, dry_run):
    stray = [k for k in data if k not in PREFECTURES]
    for key in stray:
        names = ", ".join(l["name"] for l in data[key])
        print(f"\n*** WARNING: {len(data[key])} lid(s) under non-canonical key "
              f"'{key}': {names} — resolve before deploying. ***")

    total = sum(len(v) for v in data.values())
    if dry_run:
        print(f"\n[dry-run] Would write {total} lids.")
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    print(f"\nSaved {total} lids → {path}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pokélid pipeline")
    parser.add_argument("--pokelids",  default=DEFAULT_POKELIDS)
    parser.add_argument("--stations",  default=DEFAULT_STATIONS)
    parser.add_argument("--roadside",  default=DEFAULT_ROADSIDE)
    parser.add_argument("--cities",    default=DEFAULT_CITIES)
    parser.add_argument("--output",    default=DEFAULT_OUTPUT)
    parser.add_argument("--max",       type=int, default=600, dest="max_id")
    parser.add_argument("--no-images", action="store_true")
    parser.add_argument("--dry-run",   action="store_true")
    args = parser.parse_args()

    data     = load_data(args.pokelids)
    new_keys = step_scrape(data, args.max_id, not args.no_images, args.dry_run)

    if new_keys:
        print(f"\n  {len(new_keys)} new lid(s) to complete.")
        step_stations(data, new_keys, args.stations, args.dry_run)
        step_names_ja(data, new_keys, args.dry_run)
        step_classify(data, new_keys, args.roadside, args.cities, args.dry_run)
    else:
        print("\n  No new lids — nothing to complete.")

    save_data(data, args.output, args.dry_run)


if __name__ == "__main__":
    main()
