"""
GZW Code Analysis - Extract all useful strings from executables.
Phase A: Nakama RPCs, API endpoints, game mechanics
"""

import re
import os
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "strings"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXES = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Gray Zone Warfare\GZW\Binaries\Win64\GZWClientSteam-Win64-Shipping.exe",
    r"C:\Program Files (x86)\Steam\steamapps\common\Gray Zone Warfare\GZWClientEAC.exe",
]

# Also check DLLs
DLL_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Gray Zone Warfare\GZW\Binaries\Win64"
DLLS = [os.path.join(DLL_DIR, f) for f in os.listdir(DLL_DIR) if f.endswith('.dll')]

all_files = EXES + DLLS

def extract_strings(filepath):
    """Extract ASCII and UTF-16 strings from a binary."""
    results = {
        'urls': [],
        'nakama_rpcs': [],
        'json_paths': [],
        'ue_classes': [],
        'config_keys': [],
        'endpoints': [],
        'all_strings': []
    }
    
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return results
    
    fname = os.path.basename(filepath)
    print(f"Processing {fname} ({len(data)/1024/1024:.1f} MB)...")
    
    # Extract ASCII strings
    ascii_strings = []
    current = b""
    for byte in data:
        if 32 <= byte < 127:
            current += bytes([byte])
        else:
            if len(current) >= 6:
                try:
                    ascii_strings.append(current.decode('ascii'))
                except:
                    pass
            current = b""
    if len(current) >= 6:
        try:
            ascii_strings.append(current.decode('ascii'))
        except:
            pass
    
    results['all_strings'] = ascii_strings[:50000]  # limit
    
    # 1. URLs
    for s in ascii_strings:
        if s.startswith('http://') or s.startswith('https://'):
            results['urls'].append(s)
    
    # 2. Nakama RPCs (MFGNakama.* pattern)
    for s in ascii_strings:
        if 'Nakama' in s and ('RPC' in s or 'rpc' in s or 'Function' in s or 'Error' in s or s.startswith('MFGNakama')):
            results['nakama_rpcs'].append(s)
    
    # 3. Unreal Engine class paths
    for s in ascii_strings:
        if s.startswith('/Game/') or s.startswith('/Script/') or '/Game/' in s:
            results['ue_classes'].append(s)
        elif s.startswith('Class /Script/') or s.startswith('Blueprint') or s.startswith('WidgetBlueprint'):
            results['ue_classes'].append(s)
    
    # 4. JSON-like paths
    for s in ascii_strings:
        if '/Game/' in s and s.endswith('.json') or '.json' in s:
            results['json_paths'].append(s)
    
    # 5. Config/settings keys
    for s in ascii_strings:
        if any(kw in s for kw in ['Config', 'Setting', 'Key=', 'Section=', 'CVar', 'ConsoleVariable']):
            results['config_keys'].append(s)
    
    # 6. Endpoint-like strings
    for s in ascii_strings:
        if any(kw in s for kw in ['/api/', '/v1/', '/v2/', 'Endpoint', 'endpoint', 'server', 'Server', 'host', 'Host']):
            if not s.startswith('http'):
                results['endpoints'].append(s)
    
    return results


def save_results(name, results):
    """Save extracted data to JSON files."""
    for key, items in results.items():
        if not items:
            continue
        filepath = OUTPUT_DIR / f"{name}_{key}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(sorted(set(items)), f, indent=2, ensure_ascii=False)
        print(f"  -> Saved {len(set(items))} {key} to {filepath.name}")


def generate_summary(all_results):
    """Generate a human-readable summary."""
    lines = []
    lines.append("# Gray Zone Warfare - Code Analysis Summary")
    lines.append(f"\n## Files Analyzed")
    for f in all_files:
        size = os.path.getsize(f) / 1024 / 1024 if os.path.exists(f) else 0
        lines.append(f"- {os.path.basename(f)} ({size:.1f} MB)")
    
    # Nakama RPCs
    all_nakama = set()
    for r in all_results:
        all_nakama.update(r.get('nakama_rpcs', []))
    if all_nakama:
        lines.append(f"\n## Nakama RPCs ({len(all_nakama)} found)")
        # Group by category
        categories = {}
        for rpc in sorted(all_nakama):
            parts = rpc.split('.')
            if len(parts) >= 2:
                cat = parts[0]
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(rpc)
        for cat, items in sorted(categories.items()):
            lines.append(f"\n### {cat}")
            for item in sorted(items)[:30]:
                lines.append(f"- {item}")
            if len(items) > 30:
                lines.append(f"- ... and {len(items)-30} more")
    
    # URLs
    all_urls = set()
    for r in all_results:
        all_urls.update(r.get('urls', []))
    if all_urls:
        lines.append(f"\n## URLs ({len(all_urls)} found)")
        for url in sorted(all_urls):
            lines.append(f"- {url}")
    
    # UE Classes
    all_ue = set()
    for r in all_results:
        all_ue.update(r.get('ue_classes', []))
    if all_ue:
        lines.append(f"\n## Unreal Engine Classes ({len(all_ue)} found)")
        for c in sorted(all_ue)[:50]:
            lines.append(f"- {c}")
        if len(all_ue) > 50:
            lines.append(f"- ... and {len(all_ue)-50} more")
    
    summary_path = OUTPUT_DIR.parent / "SUMMARY.md"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"\n✅ Summary saved to {summary_path}")


# Run extraction
print("=" * 60)
print("GZW Code Analysis - String Extraction")
print("=" * 60)

all_results = []
for filepath in all_files:
    if not os.path.exists(filepath):
        print(f"\nSkipping {filepath} (not found)")
        continue
    print(f"\n--- {os.path.basename(filepath)} ---")
    results = extract_strings(filepath)
    save_results(os.path.basename(filepath).replace('.', '_'), results)
    all_results.append(results)

generate_summary(all_results)
print("\nDone!")
