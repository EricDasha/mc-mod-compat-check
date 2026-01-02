import os
from typing import List, Dict, Optional
from .base import VerificationStrategy
from ..common import ModCheckResult, CheckStatus, LOADER_COMPAT, Evidence, SupportLevel
from ..api.modrinth import ModrinthClient
from ..api.curseforge import CurseForgeClient
from ..core.hashing import compute_sha1, compute_curseforge_hash

class OnlineVerificationStrategy(VerificationStrategy):
    def __init__(self, modrinth_client: ModrinthClient, curseforge_client: Optional[CurseForgeClient]):
        self.mr = modrinth_client
        self.cf = curseforge_client

    def collect_evidence(self, file_path: str, target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> List[Evidence]:
        res = self.batch_collect_evidence([file_path], target_mc, expected_loader, relaxed)
        return res.get(file_path, [])

    def batch_collect_evidence(self, file_paths: List[str], target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> Dict[str, List[Evidence]]:
        results = {fp: [] for fp in file_paths}
        
        # 1. Modrinth (SHA1)
        sha1_map = {}
        for fp in file_paths:
            s = compute_sha1(fp)
            sha1_map[s] = fp
            
        hashes = list(sha1_map.keys())
        found_in_mr = set()
        
        if hashes:
            try:
                mr_results = self.mr.get_versions_by_hashes(hashes)
                for h, version_data in mr_results.items():
                    fp = sha1_map.get(h)
                    if fp:
                        found_in_mr.add(fp)
                        evs = self._process_modrinth_evidence(version_data, target_mc, expected_loader)
                        results[fp].extend(evs)
            except Exception:
                pass
        
        # 2. CurseForge (Murmur2) - only for those not found in Modrinth
        remaining_paths = [fp for fp in file_paths if fp not in found_in_mr]
        
        if self.cf and remaining_paths:
            try:
                fp_map = {}
                for fp in remaining_paths:
                    f = compute_curseforge_hash(fp)
                    if f > 0:
                        fp_map[f] = fp
                
                fingerprints = list(fp_map.keys())
                if fingerprints:
                    cf_results = self.cf.get_fingerprint_matches(fingerprints)
                    for fid, match_data in cf_results.items():
                        fp = fp_map.get(fid)
                        if fp:
                            evs = self._process_curseforge_evidence(match_data, target_mc, expected_loader)
                            results[fp].extend(evs)
            except Exception:
                pass

        return results

    def verify(self, file_path: str, target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> Optional[ModCheckResult]:
        evidences = self.collect_evidence(file_path, target_mc, expected_loader, relaxed)
        if not evidences:
            return None
            
        # Sort by confidence
        best = sorted(evidences, key=lambda e: e.confidence, reverse=True)[0]
        
        # Map back to ModCheckResult
        status = CheckStatus.UNKNOWN
        if best.level == SupportLevel.CONFIRMED: status = CheckStatus.OK
        elif best.level == SupportLevel.LIKELY: status = CheckStatus.OK
        elif best.level == SupportLevel.POSSIBLE: status = CheckStatus.OK
        elif best.level == SupportLevel.UNSUPPORTED:
            if "loader" in best.reason.lower(): status = CheckStatus.WRONG_LOADER
            else: status = CheckStatus.WRONG_MC
            
        return ModCheckResult(
            file_name=os.path.basename(file_path),
            file_path=file_path,
            status=status,
            reason=best.reason,
            source=best.source,
            level=best.level,
            evidence=evidences
        )

    def _process_modrinth_evidence(self, data: dict, target_mc: str, expected_loader: Optional[str]) -> List[Evidence]:
        evs = []
        supported_versions = data.get("game_versions", [])
        loaders = data.get("loaders", [])
        
        # Base evidence (Found)
        evs.append(Evidence(
            source="modrinth",
            confidence=0.5, # Low confidence if no specific match
            level=SupportLevel.UNKNOWN,
            reason="Found on Modrinth, version/loader mismatch or unlisted"
        ))
        
        # MC Check
        if target_mc in supported_versions:
            evs.append(Evidence(
                source="modrinth",
                confidence=1.0,
                level=SupportLevel.CONFIRMED,
                reason=f"Modrinth lists version {target_mc}"
            ))
             
        # Loader Check
        if expected_loader:
             compat = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
             mod_loaders = [l.lower() for l in loaders]
             if not any(l in compat for l in mod_loaders):
                  evs.append(Evidence(
                    source="modrinth",
                    confidence=1.0,
                    level=SupportLevel.UNSUPPORTED,
                    reason=f"Modrinth lists loaders {loaders}, expected {expected_loader}"
                ))
        
        return evs

    def _process_curseforge_evidence(self, data: dict, target_mc: str, expected_loader: Optional[str]) -> List[Evidence]:
        evs = []
        game_versions = data.get("gameVersions", [])
        mc_vers = [v for v in game_versions if v[0].isdigit()]
        
        evs.append(Evidence(
            source="curseforge",
            confidence=0.4,
            level=SupportLevel.UNKNOWN,
            reason="Found on CurseForge, version/loader mismatch or unlisted"
        ))
        
        if target_mc in mc_vers:
            evs.append(Evidence(
                source="curseforge",
                confidence=0.8,
                level=SupportLevel.CONFIRMED, 
                reason=f"CurseForge lists version {target_mc}"
            ))
            
        if expected_loader:
            compat = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
            mod_loaders = [v.lower() for v in game_versions if not v[0].isdigit()]
            if mod_loaders:
                if not any(l in compat for l in mod_loaders):
                     evs.append(Evidence(
                        source="curseforge",
                        confidence=0.8,
                        level=SupportLevel.UNSUPPORTED,
                        reason=f"CurseForge lists loaders {mod_loaders}, expected {expected_loader}"
                    ))
        
        return evs
