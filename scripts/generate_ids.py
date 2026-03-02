#!/usr/bin/env python3
#
# generate_ids.py
# Generates stable 8-character hex IDs for each pokélid based solely on
# lat + lng + prefecture. Adding new fields to pokelid objects will never
# change existing IDs. Run this once, then re-run whenever you add new lids.
#
# Usage:
#   python3 generate_ids.py
#
# Reads:  pokelids.json
# Writes: pokelids.json (in-place, adds "id" field to each entry)
#

import json
import hashlib

def generate_id(prefecture, lat, lng):
    # Normalize to 6 decimal places to avoid float representation drift
    key = f"{prefecture}:{lat:.6f}:{lng:.6f}"
    return hashlib.sha256(key.encode()).hexdigest()[:8]

def main():
    with open("pokelids.json") as f:
        pokelids = json.load(f)

    collisions = {}
    updated = 0
    skipped = 0
    conflicts = []

    for prefecture, lids in pokelids.items():
        for lid in lids:
            lid_id = generate_id(prefecture, float(lid["lat"]), float(lid["lng"]))

            # Collision detection
            if lid_id in collisions:
                conflicts.append((lid_id, collisions[lid_id], f"{prefecture}/{lid.get('name')}"))
            collisions[lid_id] = f"{prefecture}/{lid.get('name')}"

            if lid.get("id") == lid_id:
                skipped += 1
            else:
                lid["id"] = lid_id
                updated += 1

    if conflicts:
        print(f"WARNING: {len(conflicts)} ID collision(s) detected:")
        for cid, a, b in conflicts:
            print(f"  {cid}: {a}  vs  {b}")
        print("These lids have identical lat/lng/prefecture — fix the data before proceeding.")
        return

    with open("pokelids.json", "w") as f:
        json.dump(pokelids, f, ensure_ascii=False, indent=2)

    print(f"Done. {updated} IDs added/updated, {skipped} already current.")
    print(f"Total lids: {updated + skipped}")

if __name__ == "__main__":
    main()
