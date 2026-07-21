"""
Second attempt to find AES key in GZW executable.
Search for:
- 32-byte sequences with high entropy
- AES-related patterns in Unicode
- Keys stored as byte arrays
- Known UE5 key patterns
"""
import struct
import hashlib
import os
from pathlib import Path

EXE = r"C:\Program Files (x86)\Steam\steamapps\common\Gray Zone Warfare\GZW\Binaries\Win64\GZWClientSteam-Win64-Shipping.exe"
OUTPUT_DIR = Path(r"C:\Users\jonis\Desktop\AI Reverse Engineer\projects\GrayZoneWarfare\pak_data\exports")

print("Reading executable...")
with open(EXE, 'rb') as f:
    data = f.read()

print(f"Size: {len(data)/1024/1024:.1f} MB")

# Method: Look for 32-byte sequences near specific patterns
# UE5 AES key is often stored near "PakKey" or similar
# Also try to find it looking for the encryption/decryption functions

# Look for common UE5 pak key references
patterns = [
    b'PakFile',
    b'PakKey',
    b'pakfile',
    b'pakkey', 
    b'PAKFILE',
    b'PAKEY',
    b'IoStore',
    b'iostore',
    b'IOStore',
    b'ContainerFile',
    b'container',
    b'EncryptionKey',
    b'encryption_key',
    b'Encryption',
    b'AESKey',
    b'AesKey',
    b'aes_key',
    b'PakCrypto',
    b'pak_crypto',
    b'LoaderGlobalNameHashes',
    b'GlobalNameHashes',
]

print("\nSearching for key references...")
for pattern in patterns:
    idx = 0
    while True:
        idx = data.find(pattern, idx)
        if idx == -1:
            break
        
        # Get context around the pattern
        start = max(0, idx - 64)
        end = min(len(data), idx + len(pattern) + 128)
        context = data[start:end]
        
        # Look for any 32-byte high-entropy sequences in context
        for i in range(len(context) - 32):
            chunk = context[i:i+32]
            # Count unique bytes
            unique = len(set(chunk))
            # Check if it's printable
            printable = sum(1 for b in chunk if 32 <= b < 127)
            
            if unique > 20 and printable < 10:  # High entropy, binary data
                hex_key = chunk.hex().upper()
                print(f"\n  Found near '{pattern.decode()}' at {hex(idx)}:")
                print(f"  Potential AES key: {hex_key}")
                print(f"  Format: 0x{','.join(f'{b:02x}' for b in chunk)}")
        
        idx += 1

# Also check known common keys
print("\n\nChecking against known UE5 test/development keys...")
# Some dev builds use these test keys
test_keys = [
    bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000000"),
    bytes.fromhex("0102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F20"),
]

for test_key in test_keys:
    if test_key in data:
        print(f"  Found test/dev key: {test_key.hex().upper()}")

# Also check for the key mentioned in FModel community
# GZW might have a known key by now
print("\n\nSearching for hex strings of length 64 (potential AES-256 keys)...")
# Skip to ~10MB in to avoid false positives from code
search_start = 10 * 1024 * 1024
# Search for 64 consecutive hex characters (0-9a-fA-F)
hex_positions = []
current_start = -1
for i in range(search_start, len(data)):
    b = data[i]
    if (b >= ord('0') and b <= ord('9')) or (b >= ord('a') and b <= ord('f')) or (b >= ord('A') and b <= ord('F')):
        if current_start == -1:
            current_start = i
    else:
        if current_start != -1:
            length = i - current_start
            if length >= 64:  # 32 bytes = 64 hex chars
                key_str = data[current_start:current_start+64].decode('ascii')
                hex_positions.append((current_start, key_str))
            current_start = -1

# Filter for keys that look like AES (not words)
for offset, key_str in hex_positions[:20]:
    # Check if it has enough variation to be a real key
    unique_chars = len(set(key_str.lower()))
    # Check context - what's around it
    ctx_start = max(0, offset - 30)
    ctx_end = min(len(data), offset + 94)
    context = data[ctx_start:ctx_end]
    try:
        ctx_str = context.decode('ascii', errors='replace')
        # Clean up
        ctx_clean = ''.join(c if c.isprintable() else '.' for c in ctx_str)
        print(f"\n  Hex key at {hex(offset)}: {key_str}")
        print(f"  Context: {ctx_clean}")
    except:
        pass

print("\n\nDone! If no keys found above, the PAK files are likely not encrypted.")
print("The '0 packages' issue might be a FModel compatibility problem instead.")
