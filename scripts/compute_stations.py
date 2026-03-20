#!/usr/bin/env python3
"""
compute_stations.py
═══════════════════
Computes the two train-station fields that reclassify.py depends on
but does not calculate itself:

  - nearest_station_id             (key from japan_stations.json)
  - nearest_station_distance_km    (haversine distance)

Run this first, then run reclassify.py.

Usage:
    python3 compute_stations.py
    python3 compute_stations.py --stations japan_stations.json
    python3 compute_stations.py --pokelids pokelids.json --output pokelids.json
    python3 compute_stations.py --dry-run
"""

import argparse
import json
import math
from pathlib import Path


def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dLat = (lat2 - lat1) * math.pi / 180
    dLng = (lng2 - lng1) * math.pi / 180
    a = (math.sin(dLat / 2) ** 2
         + math.cos(lat1 * math.pi / 180)
         * math.cos(lat2 * math.pi / 180)
         * math.sin(dLng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pokelids", default="data/pokelids.json")
    parser.add_argument("--stations", default="data/japan_stations.json")
    parser.add_argument("--output",   default="data/pokelids.json")
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()

    print(f"Loading pokelids : {args.pokelids}")
    pokelids = json.loads(Path(args.pokelids).read_text(encoding="utf-8"))

    print(f"Loading stations : {args.stations}")
    stations_raw = json.loads(Path(args.stations).read_text(encoding="utf-8"))
    stations = [
        (sid, s["lat"], s["lng"])
        for sid, s in stations_raw.items()
        if s.get("lat") is not None and s.get("lng") is not None
    ]
    print(f"  Valid stations: {len(stations):,} / {len(stations_raw):,}")

    total = sum(len(lids) for lids in pokelids.values())
    print(f"  Pokélids: {total:,} across {len(pokelids)} prefectures\n")

    processed = 0
    for pref, lids in pokelids.items():
        for item in lids:
            plat, plng = item["lat"], item["lng"]

            best_id, best_dist = None, float("inf")
            for sid, slat, slng in stations:
                d = haversine(plat, plng, slat, slng)
                if d < best_dist:
                    best_dist = d
                    best_id = sid

            item["nearest_station_id"]          = best_id
            item["nearest_station_distance_km"] = round(best_dist, 4)

            processed += 1
            if processed % 50 == 0:
                print(f"  {processed}/{total}...")

    print(f"\nDone. {processed} pokélids updated.")

    if args.dry_run:
        print("\n[dry-run] Sample (first lid of first prefecture):")
        first = next(iter(pokelids.values()))[0]
        print(f"  nearest_station_id         : {first['nearest_station_id']}")
        print(f"  nearest_station_distance_km: {first['nearest_station_distance_km']}")
        print("\n[dry-run] No file written.")
    else:
        Path(args.output).write_text(
            json.dumps(pokelids, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Written to {args.output}")
        print("\nNext step: run reclassify.py to update station_type and roadside fields.")


if __name__ == "__main__":
    main()
