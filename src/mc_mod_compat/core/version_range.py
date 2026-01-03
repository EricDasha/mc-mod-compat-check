import re
from typing import Optional, List, Tuple, Union

class McVersion:
    """
    Represents a Minecraft version (e.g., 1.20.1).
    Handles parsing and comparison.
    """
    def __init__(self, version_str: str):
        self.original = version_str.strip()
        self.major, self.minor, self.patch = self._parse(self.original)

    def _parse(self, s: str) -> Tuple[int, int, int]:
        # Remove any leading 'v'
        if s.lower().startswith('v'):
            s = s[1:]
            
        # Extract numeric parts: 1.20.1-rc1 -> 1, 20, 1
        parts = s.split('.')
        
        try:
            major = int(re.match(r"(\d+)", parts[0]).group(1)) if len(parts) > 0 else 0
        except (ValueError, AttributeError):
            major = 0
            
        try:
            minor = int(re.match(r"(\d+)", parts[1]).group(1)) if len(parts) > 1 else 0
        except (ValueError, AttributeError):
            minor = 0
            
        try:
            patch = int(re.match(r"(\d+)", parts[2]).group(1)) if len(parts) > 2 else 0
        except (ValueError, AttributeError):
            patch = 0
            
        return major, minor, patch

    def __repr__(self):
        return f"McVersion({self.major}.{self.minor}.{self.patch})"

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other):
        if not isinstance(other, McVersion):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other):
        if not isinstance(other, McVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other):
        return self < other or self == other

    def __gt__(self, other):
        return not (self <= other)

    def __ge__(self, other):
        return not (self < other)


class VersionRange:
    """
    Represents a range of Minecraft versions.
    Supports:
    - Exact: "1.20.1"
    - Wildcard: "1.20.x"
    - Comparison: ">=1.20", ">1.20"
    - Interval: "[1.20, 1.21)", "(1.19, 1.20]"
    """
    def __init__(self, range_str: str):
        self.range_str = range_str.strip()
        self.min_ver: Optional[McVersion] = None
        self.max_ver: Optional[McVersion] = None
        self.min_inclusive = True
        self.max_inclusive = False
        self._parse()

    def _parse(self):
        s = self.range_str
        if not s:
            return

        # Wildcard: 1.20.x
        if '.x' in s:
            base = s.replace('.x', '')
            self.min_ver = McVersion(base)
            # Create max version: 1.20 -> 1.21 (approx logic for MC)
            # Actually 1.20.x means >= 1.20.0 and < 1.21.0
            # If base is 1.20, next is 1.21. If base is 1.20.1, it's weird, but usually means patch wildcard.
            # Let's handle standard MC semantic: 1.x -> >=1.0.0 <2.0.0; 1.20.x -> >=1.20.0 <1.21.0
            
            if self.min_ver.patch == 0 and len(base.split('.')) == 2: # 1.20
                 self.max_ver = McVersion(f"{self.min_ver.major}.{self.min_ver.minor + 1}.0")
            else:
                 # 1.20.1.x ? Rare.
                 self.max_ver = McVersion(f"{self.min_ver.major}.{self.min_ver.minor}.{self.min_ver.patch + 1}") # Logic might be flawed for patch, but ok for now.
                 
            self.min_inclusive = True
            self.max_inclusive = False
            return

        # Interval: [1.20, 1.21)
        if s.startswith(('[', '(')) and s.endswith((']', ')')):
            self.min_inclusive = s.startswith('[')
            self.max_inclusive = s.endswith(']')
            content = s[1:-1]
            parts = content.split(',')
            if len(parts) == 2:
                v1, v2 = parts[0].strip(), parts[1].strip()
                if v1: self.min_ver = McVersion(v1)
                if v2: self.max_ver = McVersion(v2)
            elif len(parts) == 1:
                # [1.20] exact match?
                self.min_ver = McVersion(parts[0].strip())
                self.max_ver = self.min_ver
            return

        # Comparison: >=1.20
        if s.startswith('>='):
            self.min_ver = McVersion(s[2:])
            self.min_inclusive = True
            return
        if s.startswith('>'):
            self.min_ver = McVersion(s[1:])
            self.min_inclusive = False
            return
        if s.startswith('<='):
            self.max_ver = McVersion(s[2:])
            self.max_inclusive = True
            return
        if s.startswith('<'):
            self.max_ver = McVersion(s[1:])
            self.max_inclusive = False
            return
            
        # Single version (Exact or "Start from")?
        # In Fabric metadata, "1.20" usually means ">=1.20" or just "1.20"?
        # User says: "1.20" -> [1.20, +inf) or exact?
        # User example: ">=1.20" -> [1.20.0, +inf).
        # Let's treat plain version as Exact for safety, unless context implies otherwise.
        # BUT, the user says: "Modrinth... 'game_versions': ['1.20']... but mod actually only tested on 1.20".
        # So exact match is safer for specific lists.
        # However, for ranges, let's treat it as exact.
        self.min_ver = McVersion(s)
        self.max_ver = McVersion(s)
        self.min_inclusive = True
        self.max_inclusive = True

    def contains(self, version: Union[str, McVersion], relaxed: bool = False) -> bool:
        if isinstance(version, str):
            v = McVersion(version)
        else:
            v = version
            
        # Standard check
        in_range = True
        if self.min_ver:
            if self.min_inclusive:
                if v < self.min_ver: in_range = False
            else:
                if v <= self.min_ver: in_range = False
                
        if in_range and self.max_ver:
            if self.max_inclusive:
                if v > self.max_ver: in_range = False
            else:
                if v >= self.max_ver: in_range = False
                
        if in_range:
            return True
            
        # Relaxed logic
        if relaxed:
            # If exact match failed, try ignoring patch version
            # Only applies if this range effectively represents a single version
            if self.min_ver and self.max_ver and self.min_ver == self.max_ver:
                # Check major/minor match
                if v.major == self.min_ver.major and v.minor == self.min_ver.minor:
                    return True
                    
        return False

def parse_version_range(range_str: str) -> VersionRange:
    return VersionRange(range_str)
