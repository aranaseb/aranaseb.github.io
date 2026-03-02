#!/usr/bin/env python3
"""
reclassify.py
═════════════
Recalculates nearest-station distances and reclassifies station_type
for all pokelids, using updated roadside_stations.json.

Usage:
    python reclassify.py \
        --pokelids   pokelids.json \
        --roadside   roadside_stations.json \
        --cities     jpcities.json \
        --output     pokelids.json

All arguments are optional — defaults match the filenames above.
Re-run any time roadside_stations.json is updated (e.g. after a
fresh scrape with corrected coordinates).

Classification rules (in priority order):
  1. roadside     — nearest roadside station ≤ ROADSIDE_KM (0.5 km)
                    overrides all train-station-based types
  2. super_remote — nearest train station > SUPER_REMOTE_KM (25 km)
  3. remote       — nearest train station > REMOTE_KM (2 km)
  4. walkable     — nearest train station > WALKABLE_KM (0.5 km)
  5. major        — nearest train station ≤ WALKABLE_KM
                    AND nearest jpcity ≤ MAJOR_CITY_KM (10 km)
  6. local        — nearest train station ≤ WALKABLE_KM
                    AND nearest jpcity > MAJOR_CITY_KM

Distances updated in output:
  - nearest_roadside_station_distance_km  (to truly nearest roadside station)
  - nearest_roadside_station_id           (id of that nearest station)
  Note: nearest_station_distance_km and nearest_station_id are NOT
  recalculated here — they come from a separate train-station dataset
  not included in this pipeline.
"""

import argparse
import json
import math
import sys
from pathlib import Path

# ── Thresholds ─────────────────────────────────────────────────────────────────

ROADSIDE_KM     = 0.5   # ≤ this → roadside (overrides everything)
WALKABLE_KM     = 0.5   # ≤ this → near a train station (major or local)
REMOTE_KM       = 2   # > this → remote
SUPER_REMOTE_KM = 25.0  # > this → super_remote
MAJOR_CITY_KM   = 10.0  # ≤ this → major (when also near train station)


# ── Geometry ───────────────────────────────────────────────────────────────────

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dLat = (lat2 - lat1) * math.pi / 180
    dLng = (lng2 - lng1) * math.pi / 180
    a = (math.sin(dLat / 2) ** 2
         + math.cos(lat1 * math.pi / 180)
         * math.cos(lat2 * math.pi / 180)
         * math.sin(dLng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Classification ─────────────────────────────────────────────────────────────

def classify(
    nearest_station_km: float,
    nearest_roadside_km: float,
    nearest_city_km: float,
) -> str:
    if nearest_roadside_km <= ROADSIDE_KM:
        return "roadside"
    if nearest_station_km > SUPER_REMOTE_KM:
        return "super_remote"
    if nearest_station_km > REMOTE_KM:
        return "remote"
    if nearest_station_km > WALKABLE_KM:
        return "walkable"
    # ≤ WALKABLE_KM from a train station
    if nearest_city_km <= MAJOR_CITY_KM:
        return "major"
    return "local"


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reclassify pokelid station types.")
    parser.add_argument("--pokelids", default="pokelids.json")
    parser.add_argument("--roadside", default="roadside_stations.json")
    parser.add_argument("--cities",   default="jpcities.json")
    parser.add_argument("--output",   default="pokelids.json")
    args = parser.parse_args()

    # ── Load data ──────────────────────────────────────────────────────────────

    print(f"Loading pokelids      : {args.pokelids}")
    pokelids = json.loads(Path(args.pokelids).read_text(encoding="utf-8"))

    print(f"Loading roadside      : {args.roadside}")
    roadside_raw = json.loads(Path(args.roadside).read_text(encoding="utf-8"))
    roadside = {
        k: v for k, v in roadside_raw.items()
        if v.get("lat") is not None and v.get("lng") is not None
    }
    print(f"  Valid roadside stations: {len(roadside):,} / {len(roadside_raw):,}")

    print(f"Loading cities        : {args.cities}")
    cities = json.loads(Path(args.cities).read_text(encoding="utf-8"))

    # Pre-build lists for fast iteration
    rs_list = [(k, v["lat"], v["lng"]) for k, v in roadside.items()]
    city_list = [(c["key"], c["lat"], c["lng"]) for c in cities]

    # ── Process ────────────────────────────────────────────────────────────────

    counts_before: dict[str, int] = {}
    counts_after:  dict[str, int] = {}
    total = 0
    changed = 0

    for pref, lids in pokelids.items():
        for item in lids:
            total += 1
            plat, plng = item["lat"], item["lng"]

            # -- Nearest roadside station (full brute-force scan) ---------------
            best_rs_dist = float("inf")
            best_rs_id   = None
            for rs_id, rs_lat, rs_lng in rs_list:
                d = haversine(plat, plng, rs_lat, rs_lng)
                if d < best_rs_dist:
                    best_rs_dist = d
                    best_rs_id   = rs_id

            # -- Nearest jpcity ------------------------------------------------
            best_city_dist = float("inf")
            best_city_key  = None
            for city_key, city_lat, city_lng in city_list:
                d = haversine(plat, plng, city_lat, city_lng)
                if d < best_city_dist:
                    best_city_dist = d
                    best_city_key  = city_key

            # -- Classify ------------------------------------------------------
            old_type = item.get("station_type", "")
            new_type = classify(
                nearest_station_km  = item["nearest_station_distance_km"],
                nearest_roadside_km = best_rs_dist,
                nearest_city_km     = best_city_dist,
            )

            counts_before[old_type] = counts_before.get(old_type, 0) + 1
            counts_after[new_type]  = counts_after.get(new_type, 0) + 1

            if old_type != new_type:
                changed += 1

            # -- Update fields -------------------------------------------------
            item["station_type"]                       = new_type
            item["nearest_roadside_station_distance_km"] = round(best_rs_dist, 4)
            item["nearest_roadside_station_id"]         = best_rs_id
            item["nearest_city"]                        = best_city_key
            item["nearest_city_distance_km"]            = round(best_city_dist, 4)

    # ── Save ───────────────────────────────────────────────────────────────────

    Path(args.output).write_text(
        json.dumps(pokelids, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── Report ─────────────────────────────────────────────────────────────────

    all_types = sorted(set(list(counts_before) + list(counts_after)))
    col_w = max(len(t) for t in all_types) + 2

    print(f"\n{'─' * 48}")
    print(f"  {'Type':<{col_w}}  {'Before':>7}  {'After':>7}  {'Δ':>7}")
    print(f"{'─' * 48}")
    for t in all_types:
        b = counts_before.get(t, 0)
        a = counts_after.get(t, 0)
        delta = a - b
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        print(f"  {t:<{col_w}}  {b:>7}  {a:>7}  {delta_str:>7}")
    print(f"{'─' * 48}")
    print(f"  Total pokelids: {total}  |  Changed: {changed}")
    print(f"  Output written: {args.output}")
    print(f"{'─' * 48}\n")


if __name__ == "__main__":
    main()
