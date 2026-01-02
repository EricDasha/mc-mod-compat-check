from typing import List, Dict, Optional, Any
import os
from .base import VerificationStrategy
from ..common import ModCheckResult, CheckStatus, LOADER_COMPAT
from ..api.modrinth import ModrinthClient
from ..api.curseforge import CurseForgeClient
from ..core.hashing import compute_sha1, compute_curseforge_hash

class OnlineVerificationStrategy(VerificationStrategy):
    def __init__(self, modrinth_client: ModrinthClient, curseforge_client: Optional[CurseForgeClient]):
        self.mr = modrinth_client
        self.cf = curseforge_client

    def verify(self, file_path: str, target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> Optional[ModCheckResult]:
        # Single file verification not efficient for online, but implemented for interface.
        # It just calls batch with 1 item.
        res = self.batch_verify([file_path], target_mc, expected_loader, relaxed)
        return res.get(file_path)

    def batch_verify(self, file_paths: List[str], target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> Dict[str, ModCheckResult]:
        results = {}
        
        # 1. Modrinth (SHA1)
        sha1_map = {} # sha1 -> file_path
        for fp in file_paths:
            s = compute_sha1(fp)
            sha1_map[s] = fp
            
        hashes = list(sha1_map.keys())
        mr_results = self.mr.get_versions_by_hashes(hashes)
        
        for h, version_data in mr_results.items():
            fp = sha1_map.get(h)
            if fp:
                res = self._process_modrinth(fp, version_data, target_mc, expected_loader, relaxed)
                results[fp] = res
        
        # 2. CurseForge (Murmur2) - only for those not found in Modrinth
        remaining_paths = [fp for fp in file_paths if fp not in results]
        
        if self.cf and remaining_paths:
            fp_map = {} # fingerprint -> file_path
            for fp in remaining_paths:
                f = compute_curseforge_hash(fp)
                if f > 0:
                    fp_map[f] = fp
            
            fingerprints = list(fp_map.keys())
            cf_results = self.cf.get_fingerprint_matches(fingerprints)
            
            for fid, match_data in cf_results.items():
                fp = fp_map.get(fid)
                if fp:
                    res = self._process_curseforge(fp, match_data, target_mc, expected_loader, relaxed)
                    results[fp] = res

        return results

    def _process_modrinth(self, file_path: str, data: dict, target_mc: str, expected_loader: Optional[str], relaxed: bool) -> ModCheckResult:
        file_name = os.path.basename(file_path)
        supported_game_versions = data.get("game_versions", [])
        loaders = data.get("loaders", [])
        
        # MC Check
        mc_ok = target_mc in supported_game_versions
        # Relaxed check could be added here
        
        # Loader Check
        loader_ok = True
        if expected_loader:
             compat = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
             # Modrinth loaders are strings
             mod_loaders = [l.lower() for l in loaders]
             if not any(l in compat for l in mod_loaders):
                 loader_ok = False
        
        status = CheckStatus.OK
        if not mc_ok: status = CheckStatus.WRONG_MC
        elif not loader_ok: status = CheckStatus.WRONG_LOADER
        
        return ModCheckResult(
            file_name=file_name,
            file_path=file_path,
            status=status,
            reason=f"mr_mc:{supported_game_versions}",
            source="modrinth",
            mod_name=data.get("name"),
            mod_version=data.get("version_number"),
            url=f"https://modrinth.com/version/{data.get('id')}"
        )

    def _process_curseforge(self, file_path: str, data: dict, target_mc: str, expected_loader: Optional[str], relaxed: bool) -> ModCheckResult:
        file_name = os.path.basename(file_path)
        game_versions = data.get("gameVersions", [])
        
        # Filter game versions to find MC versions
        # CF mixes loaders and MC versions in gameVersions list
        mc_vers = [v for v in game_versions if v[0].isdigit()] # Heuristic: starts with digit
        
        mc_ok = target_mc in mc_vers
        
        loader_ok = True # CF doesn't always expose loader easily in this endpoint? 
        # Actually exactMatches usually has gameVersions which includes "Fabric", "Forge".
        
        if expected_loader:
            compat = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
            mod_loaders = [v.lower() for v in game_versions if not v[0].isdigit()]
            # If no loader info found, maybe assume OK or check if list is empty?
            if mod_loaders:
                 if not any(l in compat for l in mod_loaders):
                     loader_ok = False

        status = CheckStatus.OK
        if not mc_ok: status = CheckStatus.WRONG_MC
        elif not loader_ok: status = CheckStatus.WRONG_LOADER
        
        return ModCheckResult(
            file_name=file_name,
            file_path=file_path,
            status=status,
            reason=f"cf_mc:{mc_vers}",
            source="curseforge",
            mod_name=data.get("displayName"),
            mod_version=data.get("fileName")
        )
