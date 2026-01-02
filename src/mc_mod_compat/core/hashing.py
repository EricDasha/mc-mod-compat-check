import hashlib
import os

def compute_sha1(file_path: str) -> str:
    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()

def murmurhash2(data: bytes, seed: int = 1) -> int:
    """
    Pure Python implementation of MurmurHash2 (32-bit) used by CurseForge.
    """
    m = 0x5bd1e995
    r = 24
    length = len(data)
    h = seed ^ length

    idx = 0
    while length >= 4:
        k = (data[idx] 
             | (data[idx + 1] << 8) 
             | (data[idx + 2] << 16) 
             | (data[idx + 3] << 24))
        
        k = (k * m) & 0xFFFFFFFF
        k ^= k >> r
        k = (k * m) & 0xFFFFFFFF

        h = (h * m) & 0xFFFFFFFF
        h ^= k
        h = (h * m) & 0xFFFFFFFF

        idx += 4
        length -= 4

    if length == 3:
        h ^= data[idx + 2] << 16
    if length == 2:
        h ^= data[idx + 1] << 8
    if length == 1:
        h ^= data[idx]
        h = (h * m) & 0xFFFFFFFF

    h ^= h >> 13
    h = (h * m) & 0xFFFFFFFF
    h ^= h >> 15

    return h

def compute_curseforge_hash(file_path: str) -> int:
    """
    Compute the CurseForge fingerprint (MurmurHash2 of non-whitespace bytes).
    """
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        # Filter 0x09, 0x0A, 0x0D, 0x20
        # bytes.translate is fast
        filtered = content.translate(None, b'\x09\x0a\x0d\x20')
        return murmurhash2(filtered, 1)
    except Exception:
        return 0
