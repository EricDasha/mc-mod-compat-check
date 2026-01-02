import os
import zipfile
import json
import re
from typing import Optional
from .base import VerificationStrategy
from ..common import ModCheckResult, CheckStatus, LOADER_COMPAT
from ..core.metadata import (
    read_zip_text, 
    extract_minecraft_version_range_from_toml, 
    heuristic_detect_loader, 
    heuristic_detect_mc_versions, 
    eval_simple_constraints
)

class LocalVerificationStrategy(VerificationStrategy):
    def verify(self, file_path: str, target_mc: str, expected_loader: Optional[str] = None, relaxed: bool = False) -> Optional[ModCheckResult]:
        file_name = os.path.basename(file_path)
        
        try:
            with zipfile.ZipFile(file_path) as z:
                # 1. Fabric
                fabric_json = read_zip_text(z, "fabric.mod.json")
                if fabric_json:
                    return self._check_fabric(fabric_json, file_name, file_path, target_mc, expected_loader, relaxed)

                # 2. Forge (mods.toml)
                mods_toml = read_zip_text(z, "META-INF/mods.toml")
                if mods_toml:
                    return self._check_forge(mods_toml, file_name, file_path, target_mc, expected_loader, relaxed)

                # 3. Neoforge
                neo_toml = read_zip_text(z, "META-INF/neoforge.mods.toml")
                if neo_toml:
                    return self._check_neoforge(neo_toml, file_name, file_path, target_mc, expected_loader, relaxed)

                # 4. Quilt
                quilt_json = read_zip_text(z, "quilt.mod.json")
                if quilt_json:
                    return self._check_quilt(quilt_json, file_name, file_path, target_mc, expected_loader, relaxed)
                    
                # 5. Heuristic
                return self._check_heuristic(file_name, file_path, target_mc, expected_loader, relaxed)
                
        except Exception:
            return None
        
        return None

    def _check_fabric(self, json_text: str, file_name: str, file_path: str, target_mc: str, expected_loader: Optional[str], relaxed: bool) -> ModCheckResult:
        try:
            meta = json.loads(json_text)
        except json.JSONDecodeError:
            return ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "invalid_json", "local")

        mod_name = meta.get("name") or meta.get("id")
        mod_version = meta.get("version")

        if expected_loader and expected_loader.lower() not in ("fabric", "quilt"):
             return ModCheckResult(file_name, file_path, CheckStatus.WRONG_LOADER, "is_fabric", "local", mod_name, mod_version)

        depends = meta.get("depends", {})
        mc_dep = depends.get("minecraft") if isinstance(depends, dict) else None
        
        if not mc_dep:
            # No MC dependency declared? Assume OK or Unknown?
            # Let's return OK but with note
            return ModCheckResult(file_name, file_path, CheckStatus.OK, "no_mc_dep", "local", mod_name, mod_version)

        # Normalize mc_dep
        if isinstance(mc_dep, str):
            mc_dep = [mc_dep]
        elif isinstance(mc_dep, dict): # Detailed dependency object
             # {"version": ">=1.16"}
             v = mc_dep.get("version")
             mc_dep = [v] if v else []
        elif isinstance(mc_dep, list):
             # List of strings or objects
             new_dep = []
             for item in mc_dep:
                 if isinstance(item, str): new_dep.append(item)
                 elif isinstance(item, dict):
                     v = item.get("version")
                     if v: new_dep.append(v)
             mc_dep = new_dep

        # Check constraints
        # Logic: If ANY constraint matches (OR logic usually for list, but Fabric is tricky. usually list is AND for ranges?)
        # Actually Fabric spec: "A dependency object... or an array of dependency objects (which are OR'd)"
        # But a dependency string can be a version range.
        
        matched = False
        for c in mc_dep:
             if eval_simple_constraints(target_mc, c):
                 matched = True
                 break
        
        if matched:
            return ModCheckResult(file_name, file_path, CheckStatus.OK, f"fabric: {mc_dep}", "local", mod_name, mod_version)
        else:
            return ModCheckResult(file_name, file_path, CheckStatus.WRONG_MC, f"fabric: {mc_dep}", "local", mod_name, mod_version)

    def _check_forge(self, toml_text: str, file_name: str, file_path: str, target_mc: str, expected_loader: Optional[str], relaxed: bool) -> ModCheckResult:
        # Extract name/version regex
        m_name = re.search(r'displayName\s*=\s*"(.*?)"', toml_text)
        mod_name = m_name.group(1) if m_name else None
        
        if expected_loader and expected_loader.lower() not in ("forge", "neoforge"):
             return ModCheckResult(file_name, file_path, CheckStatus.WRONG_LOADER, "is_forge", "local", mod_name)

        mc_range = extract_minecraft_version_range_from_toml(toml_text)
        if mc_range:
            if eval_simple_constraints(target_mc, mc_range):
                 return ModCheckResult(file_name, file_path, CheckStatus.OK, f"forge: {mc_range}", "local", mod_name)
            else:
                 return ModCheckResult(file_name, file_path, CheckStatus.WRONG_MC, f"forge: {mc_range}", "local", mod_name)
        
        return ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "no_mc_range", "local", mod_name)

    def _check_neoforge(self, toml_text: str, file_name: str, file_path: str, target_mc: str, expected_loader: Optional[str], relaxed: bool) -> ModCheckResult:
         if expected_loader and expected_loader.lower() not in ("neoforge", "forge"):
             return ModCheckResult(file_name, file_path, CheckStatus.WRONG_LOADER, "is_neoforge", "local")
         
         mc_range = extract_minecraft_version_range_from_toml(toml_text)
         if mc_range:
            if eval_simple_constraints(target_mc, mc_range):
                 return ModCheckResult(file_name, file_path, CheckStatus.OK, f"neoforge: {mc_range}", "local")
            else:
                 return ModCheckResult(file_name, file_path, CheckStatus.WRONG_MC, f"neoforge: {mc_range}", "local")
         return ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "no_mc_range", "local")

    def _check_quilt(self, json_text: str, file_name: str, file_path: str, target_mc: str, expected_loader: Optional[str], relaxed: bool) -> ModCheckResult:
        try:
            meta = json.loads(json_text)
        except:
             return ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "invalid_json", "local")
             
        ql = meta.get("quilt_loader", {})
        mod_name = ql.get("metadata", {}).get("name")
        mod_version = ql.get("version")
        
        if expected_loader and expected_loader.lower() not in ("quilt", "fabric"):
             return ModCheckResult(file_name, file_path, CheckStatus.WRONG_LOADER, "is_quilt", "local", mod_name, mod_version)
             
        depends = ql.get("depends", [])
        mc_ver_limit = None
        for dep in depends:
            if isinstance(dep, dict) and dep.get("id") == "minecraft":
                mc_ver_limit = dep.get("versions")
                break
        
        if mc_ver_limit:
             if isinstance(mc_ver_limit, str):
                 if eval_simple_constraints(target_mc, mc_ver_limit):
                     return ModCheckResult(file_name, file_path, CheckStatus.OK, f"quilt: {mc_ver_limit}", "local", mod_name, mod_version)
                 else:
                     return ModCheckResult(file_name, file_path, CheckStatus.WRONG_MC, f"quilt: {mc_ver_limit}", "local", mod_name, mod_version)
        
        return ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "no_mc_dep", "local", mod_name, mod_version)

    def _check_heuristic(self, file_name: str, file_path: str, target_mc: str, expected_loader: Optional[str], relaxed: bool) -> ModCheckResult:
        det_loader = heuristic_detect_loader(file_name)
        det_versions = heuristic_detect_mc_versions(file_name)
        
        if expected_loader and det_loader:
             compat_set = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
             if det_loader.lower() not in compat_set:
                 return ModCheckResult(file_name, file_path, CheckStatus.WRONG_LOADER, f"heuristic_loader: {det_loader}", "local")
        
        if det_versions:
             # Check if target_mc matches any detected version
             # relaxed check: 1.20 matches 1.20.1?
             matched = False
             for v in det_versions:
                 if v == target_mc:
                     matched = True
                     break
                 if relaxed:
                     # 1.20 matches 1.20.x
                     if target_mc.startswith(v) or v.startswith(target_mc):
                         matched = True
                         break
             
             if matched:
                  return ModCheckResult(file_name, file_path, CheckStatus.OK, f"heuristic: {det_versions}", "local")
             else:
                  return ModCheckResult(file_name, file_path, CheckStatus.WRONG_MC, f"heuristic: {det_versions}", "local")
                  
        return ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "heuristic_failed", "local")
