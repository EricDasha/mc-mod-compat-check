import os
import zipfile
import json
import re
from typing import Optional, List, Dict
from .base import VerificationStrategy
from ..common import ModCheckResult, CheckStatus, LOADER_COMPAT, Evidence, SupportLevel
from ..core.metadata import (
    read_zip_text, 
    extract_minecraft_version_range_from_toml, 
    heuristic_detect_loader, 
    heuristic_detect_mc_versions
)
from ..core.version_range import VersionRange, McVersion

class LocalVerificationStrategy(VerificationStrategy):
    def collect_evidence(self, file_path: str, target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> List[Evidence]:
        evidences = []
        file_name = os.path.basename(file_path)
        
        try:
            with zipfile.ZipFile(file_path) as z:
                # 1. Fabric
                fabric_json = read_zip_text(z, "fabric.mod.json")
                if fabric_json:
                    evidences.extend(self._collect_fabric_evidence(fabric_json, file_name, target_mc, expected_loader))

                # 2. Forge (mods.toml)
                mods_toml = read_zip_text(z, "META-INF/mods.toml")
                if mods_toml:
                    evidences.extend(self._collect_forge_evidence(mods_toml, file_name, target_mc, expected_loader))

                # 3. Neoforge
                neo_toml = read_zip_text(z, "META-INF/neoforge.mods.toml")
                if neo_toml:
                    evidences.extend(self._collect_neoforge_evidence(neo_toml, file_name, target_mc, expected_loader))

                # 4. Quilt
                quilt_json = read_zip_text(z, "quilt.mod.json")
                if quilt_json:
                    evidences.extend(self._collect_quilt_evidence(quilt_json, file_name, target_mc, expected_loader))
                    
        except Exception:
            pass

        # 5. Heuristic (Always run as fallback or additional info)
        evidences.extend(self._collect_heuristic_evidence(file_name, target_mc, expected_loader, relaxed))
        
        return evidences

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

    def _collect_fabric_evidence(self, json_text: str, file_name: str, target_mc: str, expected_loader: Optional[str]) -> List[Evidence]:
        evs = []
        try:
            meta = json.loads(json_text)
        except json.JSONDecodeError:
            return []

        # Loader check
        if expected_loader and expected_loader.lower() not in ("fabric", "quilt"):
            evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.UNSUPPORTED,
                reason=f"Found Fabric mod, expected {expected_loader}"
            ))
            return evs 

        # MC Version check
        depends = meta.get("depends", {})
        mc_dep = depends.get("minecraft") if isinstance(depends, dict) else None
        
        if not mc_dep:
            evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.POSSIBLE,
                reason="Fabric: No explicit MC dependency"
            ))
            return evs

        # Normalize mc_dep
        if isinstance(mc_dep, str):
            mc_dep = [mc_dep]
        elif isinstance(mc_dep, dict):
            v = mc_dep.get("version")
            mc_dep = [v] if v else []
        elif isinstance(mc_dep, list):
            new_dep = []
            for item in mc_dep:
                if isinstance(item, str): new_dep.append(item)
                elif isinstance(item, dict):
                    v = item.get("version")
                    if v: new_dep.append(v)
            mc_dep = new_dep

        # Check constraints
        matched = False
        constraints = []
        for c in mc_dep:
            constraints.append(c)
            vr = VersionRange(c)
            if vr.contains(target_mc):
                matched = True
                break
        
        if matched:
            evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.POSSIBLE,
                reason=f"Fabric metadata matches: {constraints}"
            ))
        else:
            evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.UNSUPPORTED,
                reason=f"Fabric metadata requires: {constraints}"
            ))
            
        return evs

    def _collect_forge_evidence(self, toml_text: str, file_name: str, target_mc: str, expected_loader: Optional[str]) -> List[Evidence]:
        evs = []
        
        if expected_loader and expected_loader.lower() not in ("forge", "neoforge"):
             evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.UNSUPPORTED,
                reason=f"Found Forge mod, expected {expected_loader}"
            ))
             return evs

        mc_range_str = extract_minecraft_version_range_from_toml(toml_text)
        if mc_range_str:
            vr = VersionRange(mc_range_str)
            if vr.contains(target_mc):
                 evs.append(Evidence(
                    source="local_metadata",
                    confidence=0.6,
                    level=SupportLevel.POSSIBLE,
                    reason=f"Forge metadata matches: {mc_range_str}"
                ))
            else:
                 evs.append(Evidence(
                    source="local_metadata",
                    confidence=0.6,
                    level=SupportLevel.UNSUPPORTED,
                    reason=f"Forge metadata requires: {mc_range_str}"
                ))
        else:
            evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.UNKNOWN,
                reason="Forge: No MC range found"
            ))
        
        return evs

    def _collect_neoforge_evidence(self, toml_text: str, file_name: str, target_mc: str, expected_loader: Optional[str]) -> List[Evidence]:
        evs = []
        if expected_loader and expected_loader.lower() not in ("neoforge", "forge"):
             evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.UNSUPPORTED,
                reason=f"Found NeoForge mod, expected {expected_loader}"
            ))
             return evs
         
        mc_range_str = extract_minecraft_version_range_from_toml(toml_text)
        if mc_range_str:
            vr = VersionRange(mc_range_str)
            if vr.contains(target_mc):
                 evs.append(Evidence(
                    source="local_metadata",
                    confidence=0.6,
                    level=SupportLevel.POSSIBLE,
                    reason=f"NeoForge metadata matches: {mc_range_str}"
                ))
            else:
                 evs.append(Evidence(
                    source="local_metadata",
                    confidence=0.6,
                    level=SupportLevel.UNSUPPORTED,
                    reason=f"NeoForge metadata requires: {mc_range_str}"
                ))
        else:
            evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.UNKNOWN,
                reason="NeoForge: No MC range found"
            ))
        return evs

    def _collect_quilt_evidence(self, json_text: str, file_name: str, target_mc: str, expected_loader: Optional[str]) -> List[Evidence]:
        evs = []
        try:
            meta = json.loads(json_text)
        except:
            return []
             
        if expected_loader and expected_loader.lower() not in ("quilt", "fabric"):
             evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.UNSUPPORTED,
                reason=f"Found Quilt mod, expected {expected_loader}"
            ))
             return evs
             
        ql = meta.get("quilt_loader", {})
        depends = ql.get("depends", [])
        mc_ver_limit = None
        for dep in depends:
            if isinstance(dep, dict) and dep.get("id") == "minecraft":
                mc_ver_limit = dep.get("versions")
                break
        
        if mc_ver_limit:
             if isinstance(mc_ver_limit, str):
                 vr = VersionRange(mc_ver_limit)
                 if vr.contains(target_mc):
                     evs.append(Evidence(
                        source="local_metadata",
                        confidence=0.6,
                        level=SupportLevel.POSSIBLE,
                        reason=f"Quilt metadata matches: {mc_ver_limit}"
                    ))
                 else:
                     evs.append(Evidence(
                        source="local_metadata",
                        confidence=0.6,
                        level=SupportLevel.UNSUPPORTED,
                        reason=f"Quilt metadata requires: {mc_ver_limit}"
                    ))
        else:
            evs.append(Evidence(
                source="local_metadata",
                confidence=0.6,
                level=SupportLevel.POSSIBLE,
                reason="Quilt: No MC dependency"
            ))
        return evs

    def _collect_heuristic_evidence(self, file_name: str, target_mc: str, expected_loader: Optional[str], relaxed: bool) -> List[Evidence]:
        evs = []
        det_loader = heuristic_detect_loader(file_name)
        det_versions = heuristic_detect_mc_versions(file_name)
        
        # Loader check
        if expected_loader and det_loader:
             compat_set = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
             if det_loader.lower() not in compat_set:
                 evs.append(Evidence(
                    source="heuristic",
                    confidence=0.3,
                    level=SupportLevel.UNSUPPORTED,
                    reason=f"Filename suggests {det_loader}, expected {expected_loader}"
                ))
        
        # Version check
        if det_versions:
             matched = False
             for v in det_versions:
                 # Check if exact match or simple relaxed match
                 if v == target_mc:
                     matched = True
                     break
                 if relaxed:
                     if target_mc.startswith(v) or v.startswith(target_mc):
                         matched = True
                         break
             
             if matched:
                  evs.append(Evidence(
                    source="heuristic",
                    confidence=0.3,
                    level=SupportLevel.LIKELY, # Filename match is quite likely to be correct intent
                    reason=f"Filename contains version {det_versions}"
                ))
             else:
                  evs.append(Evidence(
                    source="heuristic",
                    confidence=0.3,
                    level=SupportLevel.UNSUPPORTED, # Weakly unsupported
                    reason=f"Filename contains {det_versions}, expected {target_mc}"
                ))
        
        return evs
