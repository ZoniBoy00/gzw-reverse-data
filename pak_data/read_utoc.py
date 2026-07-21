#!/usr/bin/env python3
"""Simple UE5 UTOC/UCAS reader to extract file list."""
import struct
import json
import os
import sys

PAK_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Gray Zone Warfare\GZW\Content\Paks"

def read_utoc(utoc_path):
    """Read UTOC header to understand the structure."""
    with open(utoc_path, 'rb') as f:
        data = f.read()
    
    magic = data[0:4]
    version = struct.unpack_from('<I', data, 4)[0]
    header_size = struct.unpack_from('<I', data, 8)[0]
    
    print(f"UTOC: {os.path.basename(utoc_path)}")
    print(f"  Magic: {magic}")
    print(f"  Version: {version}")
    print(f"  Header size: {header_size}")
    print(f"  File size: {len(data)}")
    
    # Try to find the directory entries
    # In UE5 UTOC, there's a compressed directory at the end
    # For now, let's search for readable strings as a workaround
    
    # Search for common UE5 file extensions
    extensions = [b'.uasset', b'.umap', b'.ubulk', b'.uexp', b'.json', b'.csv']
    
    found = []
    # Try different scan strategies
    # Strategy 1: Look for /Script/ and /Game/ paths
    for marker in [b'/Script/', b'/Game/', b'Content/']:
        offset = 0
        while True:
            pos = data.find(marker, offset)
            if pos == -1:
                break
            # Read backwards to find string start
            str_start = pos
            while str_start > 0 and data[str_start-1] != 0:
                str_start -= 1
            # Read forward to find string end  
            str_end = pos
            while str_end < len(data) and data[str_end] != 0:
                str_end += 1
            
            try:
                s = data[str_start:str_end].decode('utf-8', errors='replace')
                # Clean non-printable
                s = ''.join(c for c in s if c.isprintable() or c in '/._-()[]\\')
                if len(s) > 10 and len(s) < 500:
                    found.append(s)
            except:
                pass
            offset = pos + 1
    
    # Deduplicate and sort
    found = sorted(set(found))
    
    print(f"  Found {len(found)} paths")
    
    # Show interesting ones
    interesting = [s for s in found if any(kw in s.lower() for kw in 
        ['item', 'weapon', 'armor', 'ammo', 'quest', 'task', 'loot', 
         'datatable', 'dt_', 'data/', 'spawn', 'config', 'shop', 'trading',
         'inventory', 'storage', 'progression', 'skill', 'character',
         'npc', 'ai_', 'dialogue', 'faction', 'rep', 'attachments'])]
    
    if interesting:
        print(f"\n  === Interesting paths ({len(interesting)}) ===")
        for s in interesting[:40]:
            print(f"    {s}")
    
    return found

# Scan all UTOC files
all_paths = {}
for f in sorted(os.listdir(PAK_DIR)):
    if f.endswith('.utoc'):
        paths = read_utoc(os.path.join(PAK_DIR, f))
        all_paths[f] = paths
        print()

# Save all findings
out = {}
for f, paths in all_paths.items():
    out[f] = paths

with open(r'C:\Users\jonis\Desktop\AI Reverse Engineer\projects\GrayZoneWarfare\pak_data\exports\utoc_contents.json', 'w') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
    
print("Saved to utoc_contents.json")
