import requests
from bs4 import BeautifulSoup
import json
import re
import os
import time
from urllib.parse import urljoin, urlparse

BASE = "https://www.serebii.net/pokelids/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117 Safari/537.36"
}

OUTPUT_JSON = "data/pokelids.json"
IMAGE_DIR = "images"
DELAY = 0.5


# -------- DMS → Decimal conversion -------- #

# More flexible regex that handles various encodings and whitespace
DMS = re.compile(
    r'(\d{1,3})[°º\u00b0]\s*(\d{1,2})[\'′\u2019\u2032]\s*([\d\.]+)[\"″\u201d\u2033]\s*([NS])'
    r'\s+(\d{1,3})[°º\u00b0]\s*(\d{1,2})[\'′\u2019\u2032]\s*([\d\.]+)[\"″\u201d\u2033]\s*([EW])',
    re.IGNORECASE
)

def dms_to_dd(deg, minutes, seconds, direction):
    dd = float(deg) + float(minutes)/60 + float(seconds)/3600
    if direction.upper() in ['S', 'W']:
        dd *= -1
    return dd

def parse_dms(dms):
    # Remove non-breaking spaces and normalize whitespace
    dms = dms.replace('\xa0', ' ').replace('\u00a0', ' ')
    dms = ' '.join(dms.split())
    
    m = DMS.search(dms)
    if not m:
        # Debug: print what we couldn't parse
        print(f"  DEBUG: Could not parse: {repr(dms)}")
        return None, None
    lat = dms_to_dd(m.group(1), m.group(2), m.group(3), m.group(4))
    lng = dms_to_dd(m.group(5), m.group(6), m.group(7), m.group(8))
    return lat, lng


# -------- Discover Prefecture Links -------- #

def get_prefecture_links():
    r = requests.get(BASE, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    links = {}

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if text.endswith("Prefecture"):
            name = text.replace("Prefecture", "").strip()
            links[name] = urljoin(BASE, a["href"])

    print(f"Found {len(links)} prefectures.")
    return links


# -------- Download Image -------- #

def download_image(url, pref_name):
    parsed = urlparse(url)
    fname = os.path.basename(parsed.path)

    safe_pref = pref_name.replace(" ", "_")
    folder = os.path.join(IMAGE_DIR, safe_pref)
    os.makedirs(folder, exist_ok=True)

    local_path = os.path.join(folder, fname)

    if not os.path.exists(local_path):
        try:
            img = requests.get(url, headers=HEADERS)
            img.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(img.content)
            time.sleep(0.1)
        except Exception as e:
            print("  ERROR downloading:", url, e)
            return None

    return local_path


# -------- Scrape A Prefecture Page -------- #

def scrape_prefecture(pref, url):
    print(f"\nScraping {pref} → {url}")
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # All images: <td class="cen"><img ...></td>
    img_cells = soup.find_all("td", class_="cen")

    # All names: <td class="fooevo">Name</td>
    name_cells = soup.find_all("td", class_="fooevo")

    # All coords: <td class="fooinfo">35°xx...</td> BUT exclude valign="top"
    coord_cells = [td for td in soup.find_all("td", class_="fooinfo") 
                   if td.get("valign") != "top"]

    results = []

    # Match by index – Serebii uses tables with [IMAGE] [NAME] [COORDS]
    for img_td, name_td, coord_td in zip(img_cells, name_cells, coord_cells):

        img_tag = img_td.find("img")
        if not img_tag:
            continue

        img_url = urljoin(BASE, img_tag["src"])

        # Get the name
        name = name_td.get_text(strip=True)

        dms_text = coord_td.get_text(strip=True)
        if dms_text.startswith("Location"):
            dms_text = dms_text[8:]
        lat, lng = parse_dms(dms_text)

        if lat is None:
            print("  WARNING: DMS not parsed, enter manually:", name)
            lat,lng = 9999,9999
            dms_text = "REPLACE"

        local_path = download_image(img_url, pref)

        results.append({
            "name": name,
            "lat": lat,
            "lng": lng,
            "dms": dms_text,
            "image_url": img_url,
            "image_local": local_path
        })

    print(f" → Found {len(results)} lids.")
    return results


# -------- Main -------- #

def scrape_all():
    prefectures = get_prefecture_links()
    all_data = {}

    for pref, url in sorted(prefectures.items()):
        entries = scrape_prefecture(pref, url)
        all_data[pref.lower()] = entries
        time.sleep(DELAY)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print("\nSaved:", OUTPUT_JSON)
    return all_data


if __name__ == "__main__":
    scrape_all()
