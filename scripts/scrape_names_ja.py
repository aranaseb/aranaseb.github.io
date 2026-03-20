#!/usr/bin/env python3
#
# scrape_names_ja.py
# Fetches Japanese pokélid names from local.pokemon.jp and adds
# name_ja to each entry in pokelids.json.
#
# Run from your repo root:
#   pip install requests beautifulsoup4
#   python3 scrape_names_ja.py
#

import json
import time
import requests
from bs4 import BeautifulSoup

PREFECTURES = [
    "hokkaido","aomori","iwate","miyagi","akita","yamagata","fukushima",
    "ibaraki","tochigi","gunma","saitama","chiba","tokyo","kanagawa",
    "niigata","toyama","ishikawa","fukui","yamanashi","nagano","gifu",
    "shizuoka","aichi","mie","shiga","kyoto","osaka","hyogo","nara",
    "wakayama","tottori","shimane","okayama","hiroshima","yamaguchi",
    "tokushima","kagawa","ehime","kochi","fukuoka","saga","nagasaki",
    "kumamoto","oita","miyazaki","kagoshima","okinawa",
]

def fetch_ja_names(slug):
    url = f"https://local.pokemon.jp/manhole/{slug}.html"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    names = []
    for a in soup.select("a.manhole-detail"):
        img = a.find("img")
        if not img:
            continue
        # Text node immediately after <img> is the Japanese city name
        # e.g. <a ...><img alt="三重県/鈴鹿市">鈴鹿市</a>
        name_ja = a.get_text(strip=True)
        if not name_ja:
            # Fall back to the part after / in the alt attribute
            alt = img.get("alt", "")
            name_ja = alt.split("/")[-1] if "/" in alt else alt
        names.append(name_ja)

    return names

def main():
    with open("data/pokelids.json") as f:
        pokelids = json.load(f)

    total = sum(len(v) for v in pokelids.values())
    matched = 0
    unmatched_prefs = []

    for slug in PREFECTURES:
        lids = pokelids.get(slug)
        if not lids:
            continue

        print(f"Fetching {slug} ({len(lids)} lids)...")
        ja_names = fetch_ja_names(slug)
        print(f"  Got {len(ja_names)} JA names")

        if len(ja_names) == len(lids):
            # Counts match — assign positionally
            for lid, name_ja in zip(lids, ja_names):
                lid["name_ja"] = name_ja
            matched += len(lids)
        elif len(ja_names) > 0:
            # Count mismatch — assign what we have, flag for manual check
            print(f"  WARNING: {len(ja_names)} JA vs {len(lids)} EN — assigning positionally")
            for i, lid in enumerate(lids):
                lid["name_ja"] = ja_names[i] if i < len(ja_names) else lid["name"]
            matched += min(len(ja_names), len(lids))
            unmatched_prefs.append(f"{slug} ({len(ja_names)} JA / {len(lids)} EN)")
        else:
            print(f"  No JA names found — keeping EN names")
            for lid in lids:
                lid["name_ja"] = lid["name"]
            unmatched_prefs.append(f"{slug} (0 JA / {len(lids)} EN)")

        time.sleep(0.75)

    with open("data/pokelids.json", "w") as f:
        json.dump(pokelids, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {matched}/{total} lids updated.")
    if unmatched_prefs:
        print(f"Check these prefectures manually:")
        for p in unmatched_prefs:
            print(f"  {p}")

if __name__ == "__main__":
    main()
