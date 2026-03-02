import json

# Read the JSON file
with open('pokelids.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Clean the DMS fields
for prefecture, lids in data.items():
    for lid in lids:
        if 'dms' in lid and lid['dms'].startswith('Location'):
            lid['dms'] = lid['dms'].replace('Location', '', 1)

# Write back to file
with open('pokelids.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Cleaned DMS fields - removed 'Location' prefix from all entries")
