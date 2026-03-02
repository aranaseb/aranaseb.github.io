#!/usr/bin/env python3
"""
Japan Railway Stations Scraper
═══════════════════════════════
Two-phase scrape of Wikipedia's list of railway stations in Japan.

PHASE 1 — Letter index pages
  URL pattern: https://en.wikipedia.org/wiki/List_of_railway_stations_in_Japan:_A  (A–Z)
  For each page, find every <table> that has NO class attribute.
  In each such table, iterate rows and grab the <a href> from the FIRST <td>.
  That href is the station's Wikipedia article path — the slug is globally unique.

PHASE 2 — Individual station pages
  Visit each station's English Wikipedia page and extract from the infobox:
    english_name    ← <div class="fn org">
    japanese_name   ← <div class="nickname">
    dms_coordinates ← <span class="geo-dec">  (decimal string, e.g. "35.6895 139.6917")
    lat, lng        ← parsed from geo-dec; falls back to <span class="geo"> (DMS)

Requirements:
    pip install requests beautifulsoup4 lxml

Output:
    japan_stations.json — dict keyed by Wikipedia slug, e.g.:
    {
      "Shinjuku_Station": {
        "english_name":    "Shinjuku Station",
        "japanese_name":   "新宿駅",
        "lat":             35.6895,
        "lng":             139.6917,
        "dms_coordinates": "35.6895 139.6917"
      },
      ...
    }

Config:
    CONCURRENCY  — parallel workers for detail-page fetching (keep ≤ 5 for Wikipedia)
"""

import json
import os
import re
import time
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

# ── configuration ──────────────────────────────────────────────────────────────

BASE      = "https://en.wikipedia.org"
INDEX_URL = f"{BASE}/wiki/List_of_railway_stations_in_Japan"
LETTERS   = ["A","B","C","D","E","F","G","H","I","J","K-L","M","N","O","P","R","S","T","U","W","Y","Z"]

DELAY_BETWEEN_LETTERS = 0.4  # seconds between letter-page fetches
DELAY_BETWEEN_DETAILS = 0.4  # seconds between individual station page fetches

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "JapanStationsScraper/1.0 (educational project)"
})


# ── network ────────────────────────────────────────────────────────────────────

def get_soup(url: str, retries: int = 5) -> BeautifulSoup:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=20)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 10)) + 2
                print(f"    [429] rate limited — waiting {wait}s before retry…")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except requests.RequestException as e:
            print(f"    [warn] attempt {attempt + 1} — {url}: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {retries} attempts: {url}")


# ── coordinate parsing ─────────────────────────────────────────────────────────

def parse_geo_dec(text: str):
    """
    Parse <span class="geo-dec"> content like "35.6895 139.6917"
    or the semicolon variant "35.6895; 139.6917".
    Returns (lat, lng) floats or (None, None).
    """
    m = re.match(r"\s*(-?\d+\.?\d*)\s*[;,\s]\s*(-?\d+\.?\d*)\s*$", text.strip())
    if m:
        return round(float(m.group(1)), 6), round(float(m.group(2)), 6)
    return None, None


def dms_to_dd(text: str):
    """
    Fallback DMS parser for <span class="geo"> content like
    "35°41′25″N 139°42′02″E".
    Returns (lat, lng) floats or (None, None).
    """
    text = (text
            .replace("\u00b0", "°")
            .replace("\u2032", "'").replace("\u2033", '"')
            .replace("′", "'").replace("″", '"'))
    m = re.search(
        r"(\d+)°\s*(\d+)'\s*(\d+(?:\.\d+)?)\"\s*([NS])"
        r"\s+"
        r"(\d+)°\s*(\d+)'\s*(\d+(?:\.\d+)?)\"\s*([EW])",
        text,
    )
    if not m:
        return None, None
    ld, lm, ls, lh, nd, nm, ns, nh = m.groups()
    lat = int(ld) + int(lm) / 60 + float(ls) / 3600
    lng = int(nd) + int(nm) / 60 + float(ns) / 3600
    if lh == "S": lat = -lat
    if nh == "W": lng = -lng
    return round(lat, 6), round(lng, 6)


# ── phase 1: collect station slugs from letter-index pages ────────────────────

def collect_station_links() -> list[tuple[str, str]]:
    """
    Iterate A–Z letter pages. On each page:
      - Find every <table> that has NO class attribute.
      - For every <tr> in that table, take the FIRST <td>.
      - Extract the <a href> from that td — this is the station's wiki link.
    Returns a deduplicated list of (slug, full_url) pairs in encounter order.
    """
    all_entries: list[tuple[str, str]] = []
    seen: set[str] = set()

    for letter in LETTERS:
        url = f"{INDEX_URL}:_{letter}"
        print(f"  Collecting letter {letter}  →  {url}")
        try:
            soup = get_soup(url)
        except RuntimeError as e:
            print(f"    [skip] {e}")
            time.sleep(DELAY_BETWEEN_LETTERS)
            continue

        letter_count = 0
        # Only tables with NO class attribute
        for table in soup.find_all("table", class_=False):
            for row in table.find_all("tr"):
                tds = row.find_all("td")
                if not tds:
                    continue  # header row or empty

                first_td = tds[0]
                a = first_td.find("a", href=True)
                if not a:
                    continue

                href = a["href"]
                # Must be a plain /wiki/Article_Name link (no namespace colon)
                if not href.startswith("/wiki/"):
                    continue
                article = href[6:]           # strip /wiki/
                if ":" in article:           # skip File:, Template:, etc.
                    continue

                slug = unquote(article)
                if slug in seen:
                    continue
                seen.add(slug)
                all_entries.append((slug, BASE + href))
                letter_count += 1

        print(f"    → {letter_count} new stations (total so far: {len(all_entries)})")
        time.sleep(DELAY_BETWEEN_LETTERS)

    return all_entries


# ── phase 2: fetch each station's detail page ──────────────────────────────────

def fetch_station_detail(slug: str, wiki_url: str) -> dict:
    """
    Scrape a station's Wikipedia page. Extract:
        english_name    from  <div class="fn org">
        japanese_name   from  <div class="nickname">
        dms_coordinates from  <span class="geo-dec">
        lat, lng        parsed from geo-dec (decimal); fallback to geo (DMS)
    """
    try:
        soup = get_soup(wiki_url)
    except RuntimeError as e:
        print(f"    [skip] {slug}: {e}")
        return _empty(slug)

    # English name — class is exactly "fn org" in the vCard infobox
    fn_tag = soup.find("div", class_="fn")
    english_name = fn_tag.get_text(strip=True) if fn_tag else slug.replace("_", " ")

    # Japanese name
    nick_tag = soup.find("div", class_="nickname")
    japanese_name = nick_tag.get_text(strip=True) if nick_tag else ""

    # Coordinates — prefer geo-dec (already decimal)
    lat, lng, dms_text = None, None, ""

    geo_dec = soup.find("span", class_="geo-dec")
    if geo_dec:
        dms_text = geo_dec.get_text(strip=True)
        lat, lng = parse_geo_dec(dms_text)

    # Fallback: geo span (may be decimal "lat; lng" or full DMS)
    if lat is None:
        geo_span = soup.find("span", class_="geo")
        if geo_span:
            raw = geo_span.get_text(strip=True)
            lat, lng = parse_geo_dec(raw)
            if lat is None:
                lat, lng = dms_to_dd(raw)
            if not dms_text:
                dms_text = raw

    return {
        "english_name":    english_name,
        "japanese_name":   japanese_name,
        "lat":             lat,
        "lng":             lng,
        "dms_coordinates": dms_text or None,
    }


def _empty(slug: str) -> dict:
    return {
        "english_name":    slug.replace("_", " "),
        "japanese_name":   "",
        "lat":             None,
        "lng":             None,
        "dms_coordinates": None,
    }


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    print("═" * 60)
    print("PHASE 1 — Collecting station links from A–Z index pages")
    print("═" * 60)
    entries = collect_station_links()
    print(f"\nTotal unique stations found: {len(entries)}\n")

    print("═" * 60)
    print(f"PHASE 2 — Fetching detail pages (sequential, {DELAY_BETWEEN_DETAILS}s delay)")
    print("═" * 60)

    # Resume support: load any previously saved progress
    output_path = "japan_stations.json"
    station_dict: dict[str, dict] = {}
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            station_dict = json.load(f)
        print(f"  Resuming — {len(station_dict)} stations already fetched.\n")

    total = len(entries)
    completed = 0

    for slug, url in entries:
        # Skip already-fetched stations (resume support)
        if slug in station_dict and station_dict[slug].get("english_name") and \
                station_dict[slug]["english_name"] != slug.replace("_", " "):
            completed += 1
            continue

        try:
            station_dict[slug] = fetch_station_detail(slug, url)
        except Exception as e:
            print(f"    [error] {slug}: {e}")
            station_dict[slug] = _empty(slug)

        completed += 1
        if completed % 50 == 0 or completed == total:
            pct = completed / total * 100
            print(f"  [{completed:>5}/{total}  {pct:5.1f}%]  {slug}")
            # Save progress periodically so crashes are recoverable
            ordered_so_far = {s: station_dict[s] for s, _ in entries if s in station_dict}
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(ordered_so_far, f, ensure_ascii=False, indent=2)

        time.sleep(DELAY_BETWEEN_DETAILS)

    # Final save in original encounter order
    ordered = {slug: station_dict[slug] for slug, _ in entries if slug in station_dict}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)

    no_coords = sum(1 for v in ordered.values() if v["lat"] is None)
    print(f"\n{'═' * 60}")
    print(f"Saved  {len(ordered):,} stations  →  {output_path}")
    print(f"  With coordinates   : {len(ordered) - no_coords:,}")
    print(f"  Without coordinates: {no_coords:,}")

    print("\nSample (first 3 entries):")
    for slug, data in list(ordered.items())[:3]:
        print(f"\n  [{slug}]")
        for k, v in data.items():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
