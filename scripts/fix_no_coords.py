#!/usr/bin/env python3
"""
fix_no_coords.py
================
Resolves stations with lat=None in roadside_stations.json.

Three MLIT name-matching failure modes are fixed by improved normalisation:

  1. Full-width tilde ~ (U+FF5E) / wave dash ~ (U+301C) — NFKC maps ~ to ~
     but MLIT stores ASCII ~. Fix: normalise both to ~.

  2. Heart symbol (U+2661 etc) — strip when matching.

  3. CJK compat variant U+FA11 (looks like 崎 but isn't) — explicit remap.

  4. 道の駅 embedded mid-name — strip ALL occurrences, not just as prefix.

For genuinely post-2018 stations (not in MLIT at all), falls back to:
  - GSI geocoder (Japan's official survey institute, no key needed)
  - Nominatim (OpenStreetMap) as last resort

Usage:
    python fix_no_coords.py --input roadside_stations.json --mlit P35-18_GML.zip
    python fix_no_coords.py --input roadside_stations.json   # downloads MLIT automatically
"""

import argparse
import io
import json
import re
import time
import unicodedata
import urllib.parse
import zipfile

import requests

# ── normalisation ──────────────────────────────────────────────────────────────

_CHAR_MAP = str.maketrans({
    "\uFA11": "\u5D0E",  # 﨑 (compat) -> 崎
    "\u301C": "~",       # 〜 wave dash -> ~
    "\uFF5E": "~",       # ～ full-width tilde -> ~
    "\u2764": "",        # ❤
    "\u2661": "",        # ♡
    "\u2665": "",        # ♥
})

def normalise(name):
    name = unicodedata.normalize("NFKC", name)
    name = name.translate(_CHAR_MAP)
    name = re.sub(r"道の駅", "", name)         # strip ALL occurrences
    name = re.sub(r"[『』「」\s]", "", name)  # brackets + whitespace
    return name.strip()


# ── MLIT loader ────────────────────────────────────────────────────────────────

MLIT_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/P35/P35-18/P35-18_GML.zip"

def load_mlit(source):
    if source.startswith("http"):
        print(f"Downloading MLIT P35 ...", end=" ", flush=True)
        r = requests.get(source, timeout=60)
        r.raise_for_status()
        data = io.BytesIO(r.content)
        print("done.")
    else:
        data = open(source, "rb")

    coords = {}
    with zipfile.ZipFile(data) as zf:
        name = next(
            (n for n in zf.namelist() if re.search(r"P35.*\.geojson$", n, re.I)),
            next((n for n in zf.namelist() if n.endswith(".json")), None)
        )
        if not name:
            raise RuntimeError(f"No GeoJSON in ZIP: {zf.namelist()}")
        with zf.open(name) as f:
            gj = json.load(f)

    for feat in gj.get("features", []):
        p    = feat.get("properties", {})
        lat  = p.get("P35_001")
        lng  = p.get("P35_002")
        name = p.get("P35_006", "")
        if lat and lng and name:
            coords[normalise(name)] = (round(float(lat), 6), round(float(lng), 6))

    print(f"Loaded {len(coords):,} MLIT entries.")
    return coords


def lookup(mlit, japanese_name):
    if not japanese_name:
        return None, None, "none"
    q = normalise(japanese_name)
    if not q:
        return None, None, "none"
    if q in mlit:
        return *mlit[q], "exact"
    candidates = sorted(
        (abs(len(k) - len(q)), k, lat, lng)
        for k, (lat, lng) in mlit.items()
        if q in k or k in q
    )
    if candidates:
        _, key, lat, lng = candidates[0]
        return lat, lng, f"partial({key})"
    return None, None, "none"


# ── geocoding fallback ─────────────────────────────────────────────────────────

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "MichiNoEkiScraper/1.0 (educational)"})
JAPAN_BBOX = (24.0, 46.0, 122.0, 146.0)

def _in_japan(lat, lng):
    return JAPAN_BBOX[0] <= lat <= JAPAN_BBOX[1] and JAPAN_BBOX[2] <= lng <= JAPAN_BBOX[3]

def geocode_gsi(address):
    if not address:
        return None, None
    url = ("https://msearch.gsi.go.jp/address-search/AddressSearch"
           f"?q={urllib.parse.quote(address)}")
    try:
        r = SESSION.get(url, timeout=10)
        r.raise_for_status()
        results = r.json()
        if results:
            coords = results[0].get("geometry", {}).get("coordinates", [])
            if len(coords) == 2:
                lng, lat = float(coords[0]), float(coords[1])
                if _in_japan(lat, lng):
                    return round(lat, 6), round(lng, 6)
    except Exception as e:
        print(f"    [gsi error] {e}")
    return None, None

def geocode_nominatim(address):
    if not address:
        return None, None
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{address} Japan", "format": "json", "limit": 1, "countrycodes": "jp"},
            timeout=10,
            headers={"User-Agent": "MichiNoEkiScraper/1.0 (educational)"},
        )
        r.raise_for_status()
        results = r.json()
        if results:
            lat, lng = float(results[0]["lat"]), float(results[0]["lon"])
            if _in_japan(lat, lng):
                return round(lat, 6), round(lng, 6)
    except Exception as e:
        print(f"    [nominatim error] {e}")
    return None, None


# ── DMS ───────────────────────────────────────────────────────────────────────

def dd_to_dms(lat, lng):
    def _fmt(deg, pos, neg):
        hemi = pos if deg >= 0 else neg
        deg  = abs(deg); d = int(deg); m = int((deg-d)*60)
        s    = round((deg - d - m/60) * 3600, 1)
        return f"{d}\u00b0{m}'{(int(s) if s==int(s) else s)}\"{hemi}"
    return f"{_fmt(lat,'N','S')} {_fmt(lng,'E','W')}"


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  default="roadside_stations.json")
    ap.add_argument("--output", default=None)
    ap.add_argument("--mlit",   default=MLIT_URL)
    args = ap.parse_args()
    out  = args.output or args.input

    with open(args.input, encoding="utf-8") as f:
        stations = json.load(f)

    no_coords = {slug: v for slug, v in stations.items() if v["lat"] is None}
    print(f"Stations to fix: {len(no_coords)}\n")

    mlit = load_mlit(args.mlit)
    print()

    counts = {"exact": 0, "partial": 0, "gsi": 0, "nominatim": 0, "none": 0}

    for slug, v in no_coords.items():
        ja = v.get("japanese_name", "")
        en = v.get("address", "")

        lat, lng, match = lookup(mlit, ja)

        if lat is None:
            lat, lng = geocode_gsi(en)
            time.sleep(1.0)
            match = "gsi" if lat is not None else "none"

        if lat is None:
            lat, lng = geocode_nominatim(en)
            time.sleep(1.0)
            match = "nominatim" if lat is not None else "none"

        src = match.split("(")[0]
        counts[src] = counts.get(src, 0) + 1

        if lat is not None:
            stations[slug].update({
                "lat": lat, "lng": lng,
                "match_type": match,
                "dms_coordinates": dd_to_dms(lat, lng),
            })
            print(f"  [{src:9s}] {slug}  ja={ja!r}  -> {lat}, {lng}")
        else:
            print(f"  [FAIL     ] {slug}  ja={ja!r}")

    with open(out, "w", encoding="utf-8") as f:
        json.dump(stations, f, ensure_ascii=False, indent=2)

    still_none = sum(1 for v in stations.values() if v["lat"] is None)
    print(f"\nResults:    {counts}")
    print(f"Still None: {still_none}")
    print(f"Saved ->    {out}")

if __name__ == "__main__":
    main()
