import zipfile
import json
import re
import os
from typing import Optional, Dict, Any, List

def read_zip_text(z: zipfile.ZipFile, name: str) -> Optional[str]:
    try:
        with z.open(name) as f:
            data = f.read()
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return data.decode("utf-8-sig")
            except UnicodeDecodeError:
                return None
    except KeyError:
        return None
    except Exception:
        return None

_TOML_MINECRAFT_BLOCK_RE = re.compile(r'modId\s*=\s*["\']minecraft["\']', re.IGNORECASE)
_TOML_VERSION_RANGE_RE = re.compile(r'versionRange\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

def extract_minecraft_version_range_from_toml(toml_text: str) -> Optional[str]:
    lines = toml_text.splitlines()
    for i, line in enumerate(lines):
        if not _TOML_MINECRAFT_BLOCK_RE.search(line):
            continue
        for j in range(i, min(i + 30, len(lines))):
            m = _TOML_VERSION_RANGE_RE.search(lines[j])
            if m:
                return m.group(1).strip()
    return None

_LOADER_NAME_RE = re.compile(r'(?:^|[-_.+ ])(fabric|forge|neoforge|quilt)(?:$|[-_.+ ])', re.IGNORECASE)

def heuristic_detect_loader(name: str) -> Optional[str]:
    m = _LOADER_NAME_RE.search(name)
    if m:
        return m.group(1).lower()
    return None

def heuristic_detect_mc_versions(name: str) -> List[str]:
    s = name.lower()
    primary = [m.group(1) for m in re.finditer(r'(?:mc|minecraft|for)[-_ ]?([0-9]+\.[0-9]+(?:\.[0-9]+)?)', s)]
    if primary:
        return list(dict.fromkeys(primary))
    base = os.path.splitext(name)[0]
    tokens = re.findall(r'([0-9]+\.[0-9]+(?:\.[0-9]+)?)', base)
    if len(tokens) == 1:
        return tokens
    return []

def eval_simple_constraints(target_version: str, constraint: str) -> bool:
    """
    Very basic constraint evaluator.
    Currently only handles simple cases.
    """
    # TODO: Implement a proper SemVer parser if needed.
    # For now, we reuse the logic:
    # If constraint contains range operators, we do basic checks.
    # Else we check for substring or exact match.
    
    # Clean up constraint
    c = constraint.strip()
    if c == "*":
        return True
        
    # Handle list-like strings "[1.19,1.20)" - NOT IMPLEMENTED FULLY in original
    # We will stick to the original "simple" logic but maybe slightly improved.
    
    # If exact match
    if c == target_version:
        return True
        
    # If it's a list like "1.16.5, 1.18.2"
    if "," in c:
        parts = [p.strip() for p in c.split(",")]
        return target_version in parts

    # Fallback: check if target starts with constraint (e.g. 1.19 matches 1.19.2? No, usually other way around)
    # Original logic was very specific.
    return c in target_version # Very loose check
