"""
Parse UE5 UTOC (IO Store) format to extract file listings.

The UE5 UTOC format is documented here:
https://github.com/EpicGames/UnrealEngine/tree/ue5-main/Engine/Source/Runtime/PakFile/Public
"""

import struct
import json
import os
import zlib
from pathlib import Path

PAK_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Gray Zone Warfare\GZW\Content\Paks"
OUTPUT_DIR = Path(__file__).parent / "exports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def decompress_utoc_block(data, offset, compressed_size, uncompressed_size, compression_method):
    """Decompress a UTOC block."""
    block = data[offset:offset+compressed_size]
    
    if compression_method == 0:  # None
        return block[:uncompressed_size]
    elif compression_method == 1:  # Zlib
        try:
            return zlib.decompress(block)
        except:
            return block
    elif compression_method == 2:  # Gzip
        import gzip
        try:
            return gzip.decompress(block)
        except:
            return block
    else:
        return block


def parse_header_block(data):
    """Try to parse the first few bytes as header."""
    if len(data) < 16:
        return
    
    magic = data[0:4]
    print(f"Magic: {magic}")
    
    # Try various int interpretations
    for fmt, name in [('<I', 'LE32'), ('>I', 'BE32'), ('<Q', 'LE64'), ('>Q', 'BE64')]:
        try:
            v = struct.unpack_from(fmt, data, 4)[0]
            print(f"  Field at +4 ({name}): {v} (0x{v:x})")
        except:
            pass
        
        try:
            v = struct.unpack_from(fmt, data, 8)[0]
            print(f"  Field at +8 ({name}): {v} (0x{v:x})")
        except:
            pass
        
        try:
            v = struct.unpack_from(fmt, data, 12)[0]
            print(f"  Field at +12 ({name}): {v} (0x{v:x})")
        except:
            pass


def scan_for_strings_reverse(data, min_len=8):
    """Find strings by looking for null-byte terminated sequences."""
    results = []
    
    # Scan forward
    current = []
    for byte in data:
        if byte >= 32 and byte < 127:
            current.append(byte)
        else:
            if len(current) >= min_len:
                try:
                    s = bytes(current).decode('ascii')
                    results.append(s)
                except:
                    pass
            current = []
    if len(current) >= min_len:
        try:
            s = bytes(current).decode('ascii')
            results.append(s)
        except:
            pass
    
    return sorted(set(results))


# Process UTOC files
for fname in sorted(os.listdir(PAK_DIR)):
    if not fname.endswith('.utoc'):
        continue
    
    utoc_path = os.path.join(PAK_DIR, fname)
    ucas_path = utoc_path.replace('.utoc', '.ucas')
    
    print(f"\n{'='*60}")
    print(f"Processing: {fname}")
    print(f"{'='*60}")
    
    with open(utoc_path, 'rb') as f:
        data = f.read()
    
    print(f"Size: {len(data)} bytes")
    
    # Parse header
    parse_header_block(data)
    
    # Scan for strings
    strings = scan_for_strings_reverse(data)
    print(f"\nStrings found: {len(strings)}")
    
    # Filter for UE paths
    ue_paths = [s for s in strings if s.startswith('/') and ('/Game/' in s or '/Script/' in s or '/Engine/' in s)]
    other_paths = [s for s in strings if any(s.endswith(ext) for ext in 
        ['.uasset', '.umap', '.json', '.csv', '.locres', '.png', '.jpg', '.ogg', '.wav'])]
    
    print(f"UE paths: {len(ue_paths)}")
    for p in ue_paths[:20]:
        print(f"  {p}")
    if len(ue_paths) > 20:
        print(f"  ... and {len(ue_paths)-20} more")
    
    print(f"\nFile extensions: {len(other_paths)}")
    for p in other_paths[:20]:
        print(f"  {p}")
    
    # Save everything
    output = {
        'file': fname,
        'size': len(data),
        'all_strings': strings,
        'ue_paths': ue_paths,
        'files': other_paths,
    }
    output_path = OUTPUT_DIR / f"{fname.replace('.', '_')}_parsed.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {output_path}")
    
    # Also try to read the UCAS file for more data
    if os.path.exists(ucas_path):
        with open(ucas_path, 'rb') as f:
            ucas_data = f.read()
        ucas_strings = scan_for_strings_reverse(ucas_data[:1000000])  # first 1MB
        ucas_paths = [s for s in ucas_strings if s.startswith('/') and ('/Game/' in s or '/Script/' in s)]
        if ucas_paths:
            print(f"\nUCAS paths in first MB: {len(ucas_paths)}")
            for p in ucas_paths[:10]:
                print(f"  {p}")
            output['ucas_paths'] = ucas_paths

print("\nDone!")
