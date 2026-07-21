#!/usr/bin/env python3
"""
Generate game_assets JSON files from UTOC parsed data.
Extracts weapon, armor, ammo, medical, key, quest, and faction references.
"""
import json
import re
from pathlib import Path

BASE_DIR = Path(r"C:\Users\jonis\Desktop\AI Reverse Engineer\projects\GrayZoneWarfare")
UTOC_FILE = BASE_DIR / "pak_data" / "exports" / "GZW-WindowsClient_utoc_parsed.json"
OUTPUT_DIR = BASE_DIR / "data" / "game_assets"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load UTOC data
with open(UTOC_FILE) as f:
    data = json.load(f)

all_strings = data.get("all_strings", [])
print(f"Loaded {len(all_strings)} strings from UTOC data")

# Categorize
categories = {
    "weapons": {
        "keywords": ["weapon", "rifle", "pistol", "shotgun", "melee", "launcher", "smg", "marksman", "sniper"],
        "exclude": ["animation", "anim", "sound", "texture", "material", "ui_", "widget"],
        "items": [],
        "count": 0
    },
    "ammo": {
        "keywords": ["ammo_", "ammunition", "caliber", "bullet", "556x45", "762x39", "762x51", "9x19", "12gauge", "300blk", "57x28", "shell", "round_"],
        "exclude": ["animation", "sound", "ui_", "widget"],
        "items": [],
        "count": 0
    },
    "armor": {
        "keywords": ["armor_", "vest", "helmet", "platecarrier", "chestrig", "rig_", "carrier", "plate_", "6b45", "jpc", "lancer", "cgpc"],
        "exclude": ["animation", "anim", "sound", "ui_", "widget"],
        "items": [],
        "count": 0
    },
    "medical": {
        "keywords": ["medical", "medkit", "med_", "bandage", "splint", "health", "injury", "pain", "stress", "blood", "surgery", "firstaid"],
        "exclude": ["ui_", "widget", "sound"],
        "items": [],
        "count": 0
    },
    "keys": {
        "keywords": ["key_", "keycard", "_key", "keycard_"],
        "exclude": ["keyboard", "keybind", "keyframe", "animation", "ui_", "widget"],
        "items": [],
        "count": 0
    },
    "quests": {
        "keywords": ["quest", "task_", "mission_", "objective"],
        "exclude": ["ui_", "widget", "sound", "texture"],
        "items": [],
        "count": 0
    },
    "factions": {
        "keywords": ["faction", "criminal", "guard", "trafficker", "vendor", "merchant", "shop_"],
        "exclude": ["ui_", "widget", "texture", "sound"],
        "items": [],
        "count": 0
    }
}

# Categorize all strings
for s in all_strings:
    sl = s.lower()
    for cat_name, cat in categories.items():
        if any(k in sl for k in cat["keywords"]):
            if not any(ex in sl for ex in cat.get("exclude", [])):
                # Clean up the name
                name = s.replace('.uasset', '').replace('.ubulk', '').replace('.uexp', '')
                if name not in cat["items"]:
                    cat["items"].append(name)
                    cat["count"] += 1

# Sort and save each category
for cat_name, cat in categories.items():
    cat["items"] = sorted(set(cat["items"]))
    
    output = {
        "description": f"{cat_name.capitalize()} references found in GZW PAK files",
        "source": "UTOC string analysis (GZW-WindowsClient.utoc)",
        "total": len(cat["items"]),
        "items": cat["items"][:200],  # Limit to 200 per file
        "total_unique": len(cat["items"]),
        "note": "These are asset/reference names from the PAK table of contents, not extracted data values."
    }
    
    output_path = OUTPUT_DIR / f"{cat_name}.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"  {cat_name}.json: {len(cat['items'])} items -> {output_path}")

print(f"\nDone! All assets saved to {OUTPUT_DIR}")
