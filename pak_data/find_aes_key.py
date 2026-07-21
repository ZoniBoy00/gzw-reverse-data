"""
Search for AES encryption keys in GZW executable.
UE5 PAK files may be encrypted with AES-256 (32-byte key).
The key is typically stored as:
  1. A 32-byte sequence in the binary
  2. A hex string (64 characters)
  3. A base64 string
  4. Referenced via a specific pattern
"""

import re
import os
import hashlib
from pathlib import Path

EXE = r"C:\Program Files (x86)\Steam\steamapps\common\Gray Zone Warfare\GZW\Binaries\Win64\GZWClientSteam-Win64-Shipping.exe"
OUTPUT_DIR = Path(r"C:\Users\jonis\Desktop\AI Reverse Engineer\projects\GrayZoneWarfare\pak_data\exports")

print(f"Reading {EXE}...")
with open(EXE, 'rb') as f:
    data = f.read()

print(f"Size: {len(data)/1024/1024:.1f} MB")

# Method 1: Look for AES key patterns in strings
# AES keys are often stored as hex strings (64 hex chars)
print("\n=== Method 1: Hex string patterns (64-char hex) ===")
hex_strings = set()
for m in re.finditer(rb'[0-9a-fA-F]{60,70}', data):
    s = m.group(0).decode('ascii', errors='replace')
    # Check if it looks like a valid AES key (hex)
    if all(c in '0123456789abcdefABCDEF' for c in s):
        hex_strings.add(s)

print(f"Found {len(hex_strings)} potential hex keys")
for s in sorted(hex_strings)[:20]:
    print(f"  {s}")

# Method 2: Look for "AES" or "aes" related strings
print("\n=== Method 2: AES-related strings ===")
aes_refs = set()
for m in re.finditer(rb'[a-zA-Z0-9_]{3,50}', data):
    s = m.group(0).decode('ascii', errors='replace')
    if 'aes' in s.lower() and ('key' in s.lower() or 'encrypt' in s.lower() or 'crypto' in s.lower()):
        aes_refs.add(s)
    if s.startswith('AES') or s.startswith('aes'):
        aes_refs.add(s)

print(f"Found {len(aes_refs)} AES references:")
for s in sorted(aes_refs):
    print(f"  {s}")

# Method 3: Look for "PAK" and encryption related patterns
print("\n=== Method 3: PAK/encryption related patterns ===")
pak_refs = set()
for m in re.finditer(rb'[a-zA-Z0-9_/+]{10,100}', data):
    s = m.group(0).decode('ascii', errors='replace')
    if 'pak' in s.lower() and any(kw in s.lower() for kw in ['key', 'crypto', 'encrypt', 'aes', 'sign']):
        pak_refs.add(s)

print(f"Found {len(pak_refs)} Pak crypto references:")
for s in sorted(pak_refs):
    print(f"  {s}")

# Method 4: Look for base64 strings that decode to 32 bytes
print("\n=== Method 4: Base64 strings (potential AES keys) ===")
import base64

b64_candidates = set()
for m in re.finditer(rb'[A-Za-z0-9+/]{30,60}={0,2}', data):
    try:
        s = m.group(0).decode('ascii')
        decoded = base64.b64decode(s)
        if len(decoded) == 32:  # AES-256 key
            b64_candidates.add(s)
        elif len(decoded) == 16:  # AES-128 key
            b64_candidates.add(s)
    except:
        pass

print(f"Found {len(b64_candidates)} base64 candidates that decode to 16/32 bytes")
for s in sorted(b64_candidates)[:10]:
    try:
        decoded = base64.b64decode(s)
        print(f"  {s} -> {decoded.hex()}")
    except:
        pass

# Method 5: FModel-specific AES key storage format
# FModel uses JSON with "AESKey" field
print("\n=== Method 5: FModel AES key format ===")
# Sometimes the key is stored near "AESKey" or "aes" in the binary
for m in re.finditer(rb'.{0,100}aes.{0,100}', data, re.IGNORECASE):
    context = m.group(0)
    try:
        s = context.decode('ascii', errors='replace')
        # Look for hex keys
        hex_keys = re.findall(r'[0-9a-fA-F]{32,64}', s)
        for key in hex_keys:
            if len(key) in (32, 64):  # 16 or 32 bytes in hex
                print(f"  Found near AES: {key}")
    except:
        pass

# Method 6: Check if there's a specific key pattern UE5 uses
print("\n=== Method 6: UE5 default/known patterns ===")
# UE5 sometimes stores the key with specific markers
for marker in [b'0x', b'0x', b'AES_KEY', b'aes_key', b'PakKey', b'PAK_AES']:
    idx = data.find(marker)
    if idx >= 0:
        context = data[max(0,idx-10):idx+100]
        try:
            s = context.decode('ascii', errors='replace')
            print(f"  Found '{marker.decode()}': {s}")
        except:
            print(f"  Found '{marker.decode()}' at offset {hex(idx)}")

# Method 7: Search for 32-byte random-looking sequences near crypto references
print("\n=== Method 7: 32-byte sequences near crypto references ===")
crypto_refs = [b'crypto', b'Crypto', b'encrypt', b'Encrypt', b'decrypt', b'Decrypt', 
               b'PakFile', b'pakfile', b'Signature', b'signature', b'key', b'Key']
for ref in crypto_refs:
    idx = 0
    while True:
        idx = data.find(ref, idx)
        if idx == -1:
            break
        # Look for 32-byte sequences nearby
        nearby = data[max(0,idx-64):idx+200]
        # Try to find 32 consecutive bytes with high entropy
        for i in range(len(nearby) - 32):
            chunk = nearby[i:i+32]
            # Check entropy (rough: count unique byte values)
            if len(set(chunk)) > 20:  # High entropy = likely key material
                hex_key = chunk.hex()
                print(f"  Near '{ref.decode()}' at offset {hex(idx)}: {hex_key}")
                break
        idx += 1

# If we found candidates, save them
all_candidates = {
    'hex_strings': list(hex_strings)[:50],
    'aes_refs': list(aes_refs),
    'pak_refs': list(pak_refs),
    'b64_candidates': list(b64_candidates)[:20],
}

output_path = OUTPUT_DIR / "aes_key_candidates.json"
import json
with open(output_path, 'w') as f:
    json.dump(all_candidates, f, indent=2)
print(f"\nSaved candidates to {output_path}")
print("\nDone!")
