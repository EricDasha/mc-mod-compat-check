from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

# --- Constants ---
MODRINTH_VERSION_FILE_SHA1_URL = "https://api.modrinth.com/v2/version_file/sha1/"
MODRINTH_API_URL = "https://api.modrinth.com/v2"
CURSEFORGE_API_URL = "https://api.curseforge.com/v1"
DEFAULT_USER_AGENT = "mc-mod-compat-check/3.0 (refactored)"

CACHE_FILE_NAME = ".mod_compat_cache.json"
CONFIG_FILE_NAME = "mod_compat_config.json"

LOADER_COMPAT = {
    "fabric": {"fabric", "quilt"},
    "quilt": {"quilt", "fabric"},
    "forge": {"forge", "neoforge"},
    "neoforge": {"neoforge", "forge"},
}

KNOWN_LOADERS = {"forge", "fabric", "neoforge", "quilt", "liteloader", "rift"}

class CheckStatus(Enum):
    OK = "ok"
    WRONG_MC = "wrong_mc"
    WRONG_LOADER = "wrong_loader"
    UNKNOWN_LOADER = "unknown_loader"
    NOT_FOUND = "not_found"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"

@dataclass
class ModCheckResult:
    file_name: str
    file_path: str
    status: CheckStatus
    reason: str
    source: str = "unknown" # "modrinth", "curseforge", "local", "cache"
    mod_name: Optional[str] = None
    mod_version: Optional[str] = None
    url: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "file_path": self.file_path,
            "status": self.status.value,
            "reason": self.reason,
            "source": self.source,
            "mod_name": self.mod_name,
            "mod_version": self.mod_version,
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModCheckResult":
        return cls(
            file_name=d["file_name"],
            file_path=d["file_path"],
            status=CheckStatus(d["status"]),
            reason=d["reason"],
            source=d.get("source", "unknown"),
            mod_name=d.get("mod_name"),
            mod_version=d.get("mod_version"),
            url=d.get("url"),
        )
