"""
Analyze UE5 PAK files to find game data tables.
Uses UE5 IO store format parsing to extract file listings.
"""

import struct
import json
import os
from pathlib import Path

PAK_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Gray Zone Warfare\GZW\Content\Paks"
OUTPUT_DIR = Path(__file__).parent / "exports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_null_terminated_string(data, offset):
    """Read a null-terminated string from data at offset."""
    end = data.find(b'\x00', offset)
    if end == -1:
        return data[offset:].decode('utf-8', errors='replace'), len(data) - offset
    return data[offset:end].decode('utf-8', errors='replace'), end - offset + 1


def analyze_utoc(utoc_path):
    """Parse UE5 UTOC (table of contents) file to list PAK contents."""
    print(f"Analyzing: {utoc_path}")
    with open(utoc_path, 'rb') as f:
        data = f.read()
    
    # UTOC header
    magic = data[0:4]
    version = struct.unpack_from('<I', data, 4)[0]
    
    print(f"  Magic: {magic}")
    print(f"  Version: {version}")
    
    # UE5 UTOC format (simplified):
    # Header: magic(4) + version(4) + ... 
    # Then directory entries with hashes and offsets
    
    # Let's try to find readable strings - file paths
    strings_found = []
    search_start = 0x200  # Skip header
    
    while True:
        # Look for /Game/ or /Script/ patterns
        idx = data.find(b'/Game/', search_start)
        if idx == -1:
            idx = data.find(b'/Script/', search_start)
        if idx == -1:
            idx = data.find(b'.uasset', search_start)
        if idx == -1:
            break
        
        # Extract the string
        end_idx = data.find(b'\x00', idx)
        if end_idx == -1:
            end_idx = min(idx + 300, len(data))
        
        try:
            s = data[idx:end_idx].decode('utf-8', errors='replace')
            if len(s) > 5 and len(s) < 500:
                # Clean up the string
                s = ''.join(c for c in s if c.isprintable() or c in '/._-()[]')
                if s.strip():
                    strings_found.append(s)
        except:
            pass
        
        search_start = idx + 1
    
    # Deduplicate and sort
    strings_found = sorted(set(strings_found))
    
    print(f"  Found {len(strings_found)} file paths")
    
    # Filter for interesting data types
    datatables = [s for s in strings_found if 'DataTable' in s or 'data_table' in s.lower() or '/DT_' in s or '/Data/' in s.lower()]
    blueprints = [s for s in strings_found if s.endswith('.uasset') and ('Item' in s or 'Weapon' in s or 'Armor' in s or 'Ammo' in s)]
    jsons = [s for s in strings_found if '.json' in s.lower()]
    csvs = [s for s in strings_found if '.csv' in s.lower()]
    
    if datatables:
        print(f"\n  === DataTables ({len(datatables)}) ===")
        for dt in datatables[:30]:
            print(f"    {dt}")
    
    if jsons:
        print(f"\n  === JSON files ({len(jsons)}) ===")
        for j in jsons[:20]:
            print(f"    {j}")
    
    if csvs:
        print(f"\n  === CSV files ({len(csvs)}) ===")
        for c in csvs[:20]:
            print(f"    {c}")
    
    if blueprints:
        print(f"\n  === Game Items ({len(blueprints)}) ===")
        for bp in blueprints[:30]:
            print(f"    {bp}")
    
    # Save all strings to file
    output_path = OUTPUT_DIR / f"{Path(utoc_path).stem}_files.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_files': len(strings_found),
            'datatables': datatables,
            'blueprints': blueprints,
            'all_paths': strings_found
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  -> Saved to {output_path}")
    
    return strings_found


# Analyze all UTOC files
for f in os.listdir(PAK_DIR):
    if f.endswith('.utoc'):
        utoc_path = os.path.join(PAK_DIR, f)
        analyze_utoc(utoc_path)
        print()

print("Done!")
