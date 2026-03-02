#!/usr/bin/env python3
"""
Japan Roadside Stations (Michi-no-Eki) Scraper
════════════════════════════════════════════════
Scrapes https://michi-no-eki.com/en/guides for station details, then
looks up precise GPS coordinates from the official MLIT government dataset.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COORDINATE STRATEGY  (why everything else was unreliable)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The michi-no-eki.com pages render their map client-side (JavaScript), so
no coordinates appear in the scraped HTML.  The "Additional Info" regional
pages are inconsistent — some have Google Maps links, many don't.
Geocoding Japanese addresses with Nominatim / GSI hits ~30-40% because
the address strings vary in format (番地 vs 番, full-width numbers, etc.).

The correct solution is the authoritative government GeoJSON:

  Ministry of Land, Infrastructure, Transport and Tourism (MLIT)
  国土数値情報 道の駅データ P35 — 2018 edition (covers all ~1,200 stations)
  https://nlftp.mlit.go.jp/ksj/gml/data/P35/P35-18/P35-18_GML.zip

  Fields: P35_001=lat, P35_002=lng, P35_006=道の駅名 (Japanese station name)

We download this ZIP once, extract the GeoJSON, and build a lookup dict
keyed on the Japanese name.  Matching is done against the 「japanese_name」
scraped from michi-no-eki.com.  The MLIT data covers every registered
Michi-no-Eki so coverage is essentially 100%.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 0 — Download & parse MLIT P35 GeoJSON into a {ja_name: (lat,lng)} dict.

PHASE 1 — Paginate https://michi-no-eki.com/en/guides (pages 1–52) to
           collect every station slug and its guide-page URL.

PHASE 2 — Fetch each guide page to extract:
             english_name  — from <h1 class="text-4xl ...">
             japanese_name — text between 「 and 」
             address       — from the Essential Information block
             postal_code   — 〒XXX-XXXX from the same block
             map_code      — "Map Code: NNN NNN NNN" (DENSO car-nav code)
           Then look up (lat, lng) from the MLIT table using japanese_name.

OUTPUT  — roadside_stations.json  keyed by slug.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Requirements:
    pip install requests beautifulsoup4 lxml

Usage:
    python roadside_stations_scraper.py
"""

import io
import json
import os
import re
import time
import unicodedata
import zipfile

import requests
from bs4 import BeautifulSoup

# ── configuration ──────────────────────────────────────────────────────────────

BASE          = "https://michi-no-eki.com"
GUIDES_URL    = f"{BASE}/en/guides"
TOTAL_PAGES   = 52

PAGE_DELAY    = 1.0   # seconds between list-page fetches
DETAIL_DELAY  = 1.5   # seconds between detail-page fetches
SAVE_INTERVAL = 25    # checkpoint every N stations

OUTPUT_FILE   = "roadside_stations.json"

# MLIT P35 dataset — official government coordinates for all Michi-no-Eki
MLIT_P35_ZIP = "https://nlftp.mlit.go.jp/ksj/gml/data/P35/P35-18/P35-18_GML.zip"
# The GeoJSON inside the ZIP (filename may vary slightly):
MLIT_GEOJSON_PATTERN = re.compile(r"P35.*\.geojson$", re.I)

H3_CLASS = (
    "text-xl font-heading font-semibold text-foreground mb-3 "
    "group-hover:text-primary transition-colors line-clamp-2"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "MichiNoEkiScraper/1.0 (educational project)"})


# ── PHASE 0: MLIT coordinate table ────────────────────────────────────────────

def _normalise(name: str) -> str:
    """
    Normalise a Japanese station name for fuzzy matching:
    - NFKC (full-width → half-width digits/latin, normalise kana)
    - strip spaces and the common prefix 道の駅
    """
    name = unicodedata.normalize("NFKC", name).strip()
    name = re.sub(r"\s+", "", name)
    name = re.sub(r"^道の駅\s*", "", name)
    return name


def load_mlit_coords(zip_url: str = MLIT_P35_ZIP) -> dict[str, tuple[float, float]]:
    """
    Download the MLIT P35 ZIP once, extract the GeoJSON, and return a dict:
        { normalised_japanese_name: (lat, lng) }

    The GeoJSON feature properties are:
        P35_001  float  latitude
        P35_002  float  longitude
        P35_006  str    道の駅名  (Japanese name, may include 道の駅 prefix)
    """
    print("  Downloading MLIT P35 dataset…", end=" ", flush=True)
    try:
        r = SESSION.get(zip_url, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"\n  [MLIT download failed] {e}")
        return {}

    coords: dict[str, tuple[float, float]] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            # Find the GeoJSON file inside the ZIP
            geojson_names = [n for n in zf.namelist() if MLIT_GEOJSON_PATTERN.search(n)]
            if not geojson_names:
                # Fallback: look for any .json
                geojson_names = [n for n in zf.namelist() if n.endswith(".json")]
            if not geojson_names:
                print(f"\n  [MLIT] No GeoJSON found in ZIP. Files: {zf.namelist()[:10]}")
                return {}

            with zf.open(geojson_names[0]) as f:
                gj = json.load(f)

        for feat in gj.get("features", []):
            props = feat.get("properties", {})
            lat = props.get("P35_001") or props.get("lat")
            lng = props.get("P35_002") or props.get("lon") or props.get("lng")
            name = props.get("P35_006") or props.get("name") or ""
            if lat and lng and name:
                key = _normalise(name)
                coords[key] = (round(float(lat), 6), round(float(lng), 6))

    except Exception as e:
        print(f"\n  [MLIT parse error] {e}")
        return {}

    print(f"loaded {len(coords):,} stations.")
    return coords


def lookup_coords(
    mlit: dict[str, tuple[float, float]],
    japanese_name: str,
) -> tuple[float | None, float | None, str]:
    """
    Look up (lat, lng) for a station by Japanese name.
    Returns (lat, lng, match_type) or (None, None, 'none').

    Match types tried in order:
      exact   — normalised name matches directly
      strip   — strip 道の駅 prefix from both sides and retry
      partial — MLIT key starts with or contains the query (or vice-versa)
    """
    if not japanese_name:
        return None, None, "none"

    q = _normalise(japanese_name)
    if not q:
        return None, None, "none"

    # exact
    if q in mlit:
        lat, lng = mlit[q]
        return lat, lng, "exact"

    # partial: check if query is contained in any key or vice-versa
    # (handles cases like "道の駅三笠" vs "三笠" or "三笠ジオパーク")
    candidates = []
    for key, (lat, lng) in mlit.items():
        if q in key or key in q:
            # prefer shorter (more specific) keys
            candidates.append((abs(len(key) - len(q)), key, lat, lng))

    if candidates:
        candidates.sort()
        _, matched_key, lat, lng = candidates[0]
        return lat, lng, f"partial({matched_key})"

    return None, None, "none"


# ── network helpers ────────────────────────────────────────────────────────────

def get_soup(url: str, retries: int = 5) -> BeautifulSoup:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=20)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 15)) + 2
                print(f"    [429] waiting {wait}s…")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except requests.RequestException as e:
            print(f"    [warn] attempt {attempt + 1} — {url}: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {retries} attempts: {url}")


# ── DMS conversion ─────────────────────────────────────────────────────────────

def dd_to_dms(lat: float, lng: float) -> str:
    def _fmt(deg, pos, neg):
        hemi  = pos if deg >= 0 else neg
        deg   = abs(deg)
        d     = int(deg)
        m     = int((deg - d) * 60)
        s     = round((deg - d - m / 60) * 3600, 1)
        s_str = str(int(s)) if s == int(s) else str(s)
        return f"{d}°{m}'{s_str}\"{hemi}"
    return f"{_fmt(lat, 'N', 'S')} {_fmt(lng, 'E', 'W')}"


# ── PHASE 1: collect slugs ─────────────────────────────────────────────────────

def collect_station_links() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()

    for page in range(1, TOTAL_PAGES + 1):
        url = f"{GUIDES_URL}?page={page}"
        print(f"  Page {page:>2}/{TOTAL_PAGES}  →  {url}")
        try:
            soup = get_soup(url)
        except RuntimeError as e:
            print(f"    [skip] {e}")
            time.sleep(PAGE_DELAY)
            continue

        page_count = 0
        for h3 in soup.find_all("h3", class_=H3_CLASS):
            a = h3.find_parent("a", href=True)
            if not a:
                for parent in h3.parents:
                    if parent.name == "a" and parent.get("href"):
                        a = parent
                        break
            if not a:
                continue

            href  = a["href"]
            slug  = href.rstrip("/").split("/")[-1]
            if slug in seen:
                continue
            seen.add(slug)
            detail_url = BASE + href if href.startswith("/") else href
            entries.append((slug, detail_url))
            page_count += 1

        print(f"    → {page_count} stations  (total: {len(entries)})")
        time.sleep(PAGE_DELAY)

    return entries


# ── PHASE 2: detail pages ─────────────────────────────────────────────────────

def fetch_station_detail(
    slug: str,
    url: str,
    mlit: dict[str, tuple[float, float]],
) -> dict:
    try:
        soup = get_soup(url)
    except RuntimeError as e:
        print(f"    [skip] {slug}: {e}")
        return _empty(slug)

    # ── English name ──────────────────────────────────────────────────────────
    h1 = soup.find("h1", class_=re.compile(r"text-4xl"))
    raw_name     = h1.get_text(strip=True) if h1 else ""
    english_name = re.sub(r"^Station\s+", "", raw_name).strip() or \
                   slug.replace("-", " ").title()

    # ── Japanese name (between 「 and 」) ─────────────────────────────────────
    japanese_name = ""
    ja_span = soup.find("span", class_="font-locale-ja")
    if ja_span:
        m = re.search(r"「(.+?)」", ja_span.get_text(strip=True))
        if m:
            japanese_name = m.group(1)
    if not japanese_name:
        m = re.search(r"「(.+?)」", soup.get_text(" ", strip=True))
        if m:
            japanese_name = m.group(1)

    # ── Address, postal code, map code ───────────────────────────────────────
    english_address = ""
    postal_code     = ""
    map_code        = ""

    info_div = soup.find("div", class_=lambda c: c and "space-y-4" in c and "text-sm" in c)
    if info_div:
        wrapper = info_div.find("div", recursive=False)
        if wrapper:
            gcs = wrapper.find_all("div", recursive=False)
            if len(gcs) >= 2:
                english_address = gcs[1].get_text(strip=True)
            if len(gcs) >= 3:
                raw_pc = gcs[2].get_text(strip=True)
                m = re.search(r"\d{3}-\d{4}", raw_pc)
                if m:
                    postal_code = m.group(0)

    # Map Code appears as plain text "Map Code\n180 276 269"
    full_text = soup.get_text(" ", strip=True)
    mc = re.search(r"Map\s*Code\s*[:\s]*(\d[\d\s*]+\d)", full_text)
    if mc:
        map_code = re.sub(r"\s+", " ", mc.group(1).strip())

    # ── Coordinates from MLIT lookup ─────────────────────────────────────────
    lat, lng, match_type = lookup_coords(mlit, japanese_name)

    if lat is None:
        print(f"    [no coords] {slug!r}  ja={japanese_name!r}")
    else:
        print(f"    [{match_type}] {slug}  ja={japanese_name!r}  → {lat}, {lng}")

    dms = dd_to_dms(lat, lng) if lat is not None else None

    return {
        "english_name":  english_name,
        "japanese_name": japanese_name,
        "address":       english_address,
        "postal_code":   postal_code,
        "map_code":      map_code,
        "lat":           lat,
        "lng":           lng,
        "match_type":    match_type,
        "dms_coordinates": dms,
    }


def _empty(slug: str) -> dict:
    return {
        "english_name":    slug.replace("-", " ").title(),
        "japanese_name":   "",
        "address":         "",
        "postal_code":     "",
        "map_code":        "",
        "lat":             None,
        "lng":             None,
        "match_type":      "none",
        "dms_coordinates": None,
    }


def save(data: dict, entries: list):
    ordered = {slug: data[slug] for slug, _ in entries if slug in data}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    # ── Phase 0: MLIT coordinate table ───────────────────────────────────────
    print("═" * 62)
    print("PHASE 0 — Loading MLIT P35 coordinate table")
    print("═" * 62)
    mlit = load_mlit_coords()
    if not mlit:
        print("  WARNING: MLIT data unavailable — no coordinates will be set.")

    # ── Phase 1: collect slugs ────────────────────────────────────────────────
    print()
    print("═" * 62)
    print("PHASE 1 — Collecting station links from guide pages")
    print("═" * 62)
    entries = collect_station_links()
    print(f"\nTotal unique stations: {len(entries)}\n")

    # ── Phase 2: detail pages ─────────────────────────────────────────────────
    print("═" * 62)
    print("PHASE 2 — Fetching detail pages + MLIT coord lookup")
    print("═" * 62)

    station_dict: dict[str, dict] = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            station_dict = json.load(f)
        print(f"  Resuming — {len(station_dict)} stations already saved.\n")

    total     = len(entries)
    completed = 0

    for slug, url in entries:
        existing = station_dict.get(slug)
        # Skip only if we already have a real english name AND coordinates
        if existing \
                and existing.get("english_name") \
                and existing["english_name"] != slug.replace("-", " ").title() \
                and existing.get("lat") is not None:
            completed += 1
            continue

        station_dict[slug] = fetch_station_detail(slug, url, mlit)
        completed += 1

        if completed % SAVE_INTERVAL == 0 or completed == total:
            pct = completed / total * 100
            print(f"  [{completed:>4}/{total}  {pct:5.1f}%]  checkpoint saved")
            save(station_dict, entries)

        time.sleep(DETAIL_DELAY)

    save(station_dict, entries)

    # ── Summary ───────────────────────────────────────────────────────────────
    no_coords = sum(1 for v in station_dict.values() if v["lat"] is None)
    no_ja     = sum(1 for v in station_dict.values() if not v["japanese_name"])
    by_match: dict[str, int] = {}
    for v in station_dict.values():
        k = v.get("match_type", "none").split("(")[0]  # strip partial detail
        by_match[k] = by_match.get(k, 0) + 1

    print(f"\n{'═' * 62}")
    print(f"Saved  {len(station_dict):,} stations  →  {OUTPUT_FILE}")
    print(f"  With coordinates   : {len(station_dict) - no_coords:,}")
    print(f"  Without coordinates: {no_coords:,}")
    print(f"  Missing Japanese   : {no_ja:,}")
    print(f"  Match breakdown    : {by_match}")

    print("\nSample (first 3 entries):")
    for slug, data in list(station_dict.items())[:3]:
        print(f"\n  [{slug}]")
        for k, v in data.items():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
