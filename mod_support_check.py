import argparse
import os
import sys
import hashlib
import urllib.request
import urllib.error
import json
import re
import zipfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import locale

# --- I18n ---
CURRENT_LANG = "zh_CN"

LANG_NAMES = {
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "ja_JP": "日本語",
    "ko_KR": "한국어",
    "en_US": "English"
}

TRANSLATIONS = {
    "zh_CN": {
        "title": "Mod 版本支持检测工具",
        "mc_version": "Minecraft 版本:",
        "loader": "加载器:",
        "mod_dir": "Mod 目录:",
        "browse": "浏览...",
        "start_check": "开始检测",
        "network_check": "启用联网检查 (Modrinth)",
        "col_filename": "文件名",
        "col_modname": "Mod名称",
        "col_version": "版本",
        "col_loader": "加载器",
        "col_constraint": "版本限制",
        "col_drop": "Drop ID",
        "col_status": "状态",
        "status_compat": "兼容",
        "status_incompat": "不兼容",
        "status_unknown": "未知",
        "status_loader_mismatch": "加载器不匹配",
        "msg_dir_not_exist": "目录不存在",
        "msg_select_dir": "请选择 Mod 目录",
        "msg_checking": "正在检测...",
        "msg_done": "检测完成",
        "lang_select": "语言 / Language",
        "cli_desc": "Minecraft Mod 版本兼容性检测工具",
        "cli_ver_help": "目标 Minecraft 版本 (例如 1.20.1)",
        "cli_loader_help": "目标加载器类型",
        "cli_dir_help": "Mod 文件夹路径",
        "cli_net_help": "启用联网检查",
        "checking_console": "正在检测 {dir} (MC: {ver}, Loader: {ldr})...",
        "net_check_console": "联网检查: {file}..."
    },
    "zh_TW": {
        "title": "Mod 版本支援檢測工具",
        "mc_version": "Minecraft 版本:",
        "loader": "載入器:",
        "mod_dir": "Mod 目錄:",
        "browse": "瀏覽...",
        "start_check": "開始檢測",
        "network_check": "啟用聯網檢查 (Modrinth)",
        "col_filename": "檔名",
        "col_modname": "Mod名稱",
        "col_version": "版本",
        "col_loader": "載入器",
        "col_constraint": "版本限制",
        "col_drop": "Drop ID",
        "col_status": "狀態",
        "status_compat": "相容",
        "status_incompat": "不相容",
        "status_unknown": "未知",
        "status_loader_mismatch": "載入器不匹配",
        "msg_dir_not_exist": "目錄不存在",
        "msg_select_dir": "請選擇 Mod 目錄",
        "msg_checking": "正在檢測...",
        "msg_done": "檢測完成",
        "lang_select": "語言 / Language",
        "cli_desc": "Minecraft Mod 版本相容性檢測工具",
        "cli_ver_help": "目標 Minecraft 版本 (例如 1.20.1)",
        "cli_loader_help": "目標載入器類型",
        "cli_dir_help": "Mod 資料夾路徑",
        "cli_net_help": "啟用聯網檢查",
        "checking_console": "正在檢測 {dir} (MC: {ver}, Loader: {ldr})...",
        "net_check_console": "聯網檢查: {file}..."
    },
    "ja_JP": {
        "title": "Mod バージョン対応チェックツール",
        "mc_version": "Minecraft バージョン:",
        "loader": "ローダー:",
        "mod_dir": "Mod ディレクトリ:",
        "browse": "参照...",
        "start_check": "チェック開始",
        "network_check": "オンラインチェックを有効化 (Modrinth)",
        "col_filename": "ファイル名",
        "col_modname": "Mod名",
        "col_version": "バージョン",
        "col_loader": "ローダー",
        "col_constraint": "バージョン制限",
        "col_drop": "Drop ID",
        "col_status": "ステータス",
        "status_compat": "対応",
        "status_incompat": "非対応",
        "status_unknown": "不明",
        "status_loader_mismatch": "ローダー不一致",
        "msg_dir_not_exist": "ディレクトリが存在しません",
        "msg_select_dir": "Mod ディレクトリを選択してください",
        "msg_checking": "チェック中...",
        "msg_done": "完了",
        "lang_select": "言語 / Language",
        "cli_desc": "Minecraft Mod バージョン互換性チェックツール",
        "cli_ver_help": "ターゲット Minecraft バージョン (例: 1.20.1)",
        "cli_loader_help": "ターゲットローダータイプ",
        "cli_dir_help": "Mod フォルダパス",
        "cli_net_help": "オンラインチェックを有効化",
        "checking_console": "{dir} をチェック中 (MC: {ver}, Loader: {ldr})...",
        "net_check_console": "オンラインチェック: {file}..."
    },
    "ko_KR": {
        "title": "Mod 버전 호환성 검사 도구",
        "mc_version": "Minecraft 버전:",
        "loader": "로더:",
        "mod_dir": "Mod 디렉토리:",
        "browse": "찾아보기...",
        "start_check": "검사 시작",
        "network_check": "네트워크 검사 활성화 (Modrinth)",
        "col_filename": "파일 이름",
        "col_modname": "Mod 이름",
        "col_version": "버전",
        "col_loader": "로더",
        "col_constraint": "버전 제한",
        "col_drop": "Drop ID",
        "col_status": "상태",
        "status_compat": "호환됨",
        "status_incompat": "호환되지 않음",
        "status_unknown": "알 수 없음",
        "status_loader_mismatch": "로더 불일치",
        "msg_dir_not_exist": "디렉토리가 존재하지 않습니다",
        "msg_select_dir": "Mod 디렉토리를 선택하십시오",
        "msg_checking": "검사 중...",
        "msg_done": "완료",
        "lang_select": "언어 / Language",
        "cli_desc": "Minecraft Mod 버전 호환성 검사 도구",
        "cli_ver_help": "대상 Minecraft 버전 (예: 1.20.1)",
        "cli_loader_help": "대상 로더 유형",
        "cli_dir_help": "Mod 폴더 경로",
        "cli_net_help": "네트워크 검사 활성화",
        "checking_console": "{dir} 검사 중 (MC: {ver}, Loader: {ldr})...",
        "net_check_console": "네트워크 검사: {file}..."
    },
    "en_US": {
        "title": "Mod Support Check Tool",
        "mc_version": "Minecraft Version:",
        "loader": "Loader:",
        "mod_dir": "Mod Directory:",
        "browse": "Browse...",
        "start_check": "Start Check",
        "network_check": "Enable Network Check (Modrinth)",
        "col_filename": "Filename",
        "col_modname": "Mod Name",
        "col_version": "Version",
        "col_loader": "Loader",
        "col_constraint": "Constraint",
        "col_drop": "Drop ID",
        "col_status": "Status",
        "status_compat": "Compatible",
        "status_incompat": "Incompatible",
        "status_unknown": "Unknown",
        "status_loader_mismatch": "Loader Mismatch",
        "msg_dir_not_exist": "Directory does not exist",
        "msg_select_dir": "Please select Mod directory",
        "msg_checking": "Checking...",
        "msg_done": "Done",
        "lang_select": "Language / Language",
        "cli_desc": "Minecraft Mod Compatibility Check Tool",
        "cli_ver_help": "Target Minecraft Version (e.g. 1.20.1)",
        "cli_loader_help": "Target Loader Type",
        "cli_dir_help": "Mod Folder Path",
        "cli_net_help": "Enable Network Check",
        "checking_console": "Checking {dir} (MC: {ver}, Loader: {ldr})...",
        "net_check_console": "Network checking: {file}..."
    }
}

def T(key):
    return TRANSLATIONS.get(CURRENT_LANG, TRANSLATIONS["en_US"]).get(key, key)

def detect_system_lang():
    try:
        lang = locale.getdefaultlocale()[0]
        if lang:
            if "zh" in lang:
                if "TW" in lang or "HK" in lang:
                    return "zh_TW"
                return "zh_CN"
            if "ja" in lang:
                return "ja_JP"
            if "ko" in lang:
                return "ko_KR"
    except:
        pass
    return "en_US"

CURRENT_LANG = detect_system_lang()
if CURRENT_LANG not in TRANSLATIONS:
    CURRENT_LANG = "en_US"

# --- PCL Compatibility Logic ---

def pcl_version_to_drop(version, allow_snapshot=False):
    """
    Replicates PCL's McVersion.VersionToDrop
    """
    if not version:
        return 0
    if not allow_snapshot and "-" in version:
        return 0
    
    # Remove snapshot suffix for parsing
    v_clean = version.split("-")[0]
    segments = v_clean.split(".")
    if len(segments) < 2:
        return 0
    
    try:
        major = int(segments[0])
        minor = int(segments[1])
    except ValueError:
        return 0
        
    if major == 1:
        return minor * 10
    elif major < 25:
        return 0
    else:
        return major * 10 + minor

def pcl_drop_to_version(drop):
    """
    Replicates PCL's McVersion.DropToVersion
    """
    if drop >= 250:
        return f"{drop // 10}.{drop % 10}"
    else:
        return f"1.{drop // 10}"

def pcl_is_format_fit(version):
    """
    Replicates PCL's McVersion.IsFormatFit
    """
    if not version:
        return False
    if re.match(r"^1\.\d", version):
        return True
    m = re.match(r"^([2-9]\d)\.\d+", version)
    if m and int(m.group(1)) > 25:
        return True
    return False

# --- Core Logic & Classes ---

class CompFile:
    """
    Replicates structure of PCL's CompFile for network/API results.
    """
    def __init__(self, data=None, source="local"):
        self.id = None
        self.display_name = None
        self.version = None
        self.game_versions = []
        self.loaders = []
        self.description = None
        self.source = source
        
        if data:
            self.load_from_data(data)

    def load_from_data(self, data):
        # Placeholder for loading from API JSON
        pass

class McMod:
    """
    Replicates PCL's McMod class for local file handling.
    """
    def __init__(self, path):
        self.path = path
        self.file_name = os.path.basename(path)
        self.display_name = None
        self.version = None
        self.description = None
        self.loaders = set()
        self.mc_constraint = None
        self.modrinth_hash = None
        self.comp_file = None # Associated network info
        
        self.load_metadata()

    def get_modrinth_hash(self):
        if self.modrinth_hash:
            return self.modrinth_hash
        try:
            sha1 = hashlib.sha1()
            with open(self.path, 'rb') as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    sha1.update(data)
            self.modrinth_hash = sha1.hexdigest()
            return self.modrinth_hash
        except Exception:
            return None

    def load_metadata(self):
        if not os.path.isfile(self.path):
            return
        
        # PCL logic: check extensions
        lower_path = self.path.lower()
        valid_exts = (".jar", ".zip", ".litemod", ".jar.disabled", ".zip.disabled", ".litemod.disabled", ".jar.old", ".zip.old", ".litemod.old")
        if not any(lower_path.endswith(ext) for ext in valid_exts):
            return

        try:
            with zipfile.ZipFile(self.path, "r") as zf:
                entries_text = {}
                # PCL reads these specific files
                target_files = [
                    "mcmod.info", 
                    "fabric.mod.json", 
                    "quilt.mod.json", "quilt_loader.json", 
                    "META-INF/mods.toml", "META-INF/neoforge.mods.toml", 
                    "META-INF/fml_cache_annotation.json", 
                    "META-INF/MANIFEST.MF"
                ]
                
                # Check for existence first to avoid exceptions on open
                namelist = zf.namelist()
                for target in target_files:
                    if target in namelist:
                        entries_text[target] = read_zip_text(zf, target)

                self.detect_loader(entries_text, namelist)
                self.parse_metadata(entries_text)

        except Exception as e:
            # print(f"Error reading {self.path}: {e}")
            pass

    def detect_loader(self, entries, namelist):
        self.loaders = set()
        
        if "fabric.mod.json" in entries:
            self.loaders.add("fabric")
            
        if "quilt.mod.json" in entries or "quilt_loader.json" in entries:
            self.loaders.add("quilt")
            
        if "META-INF/mods.toml" in entries or "META-INF/neoforge.mods.toml" in entries:
            # Check content for neoforge
            text = entries.get("META-INF/neoforge.mods.toml") or entries.get("META-INF/mods.toml")
            if text and "modLoader" in text and "neoforge" in text.lower():
                self.loaders.add("neoforge")
            else:
                self.loaders.add("forge")
                
        if self.path.lower().endswith(".litemod"):
            self.loaders.add("liteloader")

    def parse_metadata(self, entries):
        # 1. mcmod.info
        if "mcmod.info" in entries:
            try:
                obj = parse_json(entries["mcmod.info"])
                if obj:
                    o = obj[0] if isinstance(obj, list) and obj else (obj.get("modList", [{}])[0] if isinstance(obj, dict) else None)
                    if isinstance(o, dict):
                        self.display_name = o.get("name")
                        self.description = o.get("description")
                        self.version = parse_version_string(o.get("version"))
            except: pass

        # 2. fabric.mod.json
        if "fabric.mod.json" in entries:
            try:
                fo = parse_json(entries["fabric.mod.json"])
                if isinstance(fo, dict):
                    self.display_name = fo.get("name") or self.display_name
                    self.description = fo.get("description") or self.description
                    self.version = parse_version_string(fo.get("version")) or self.version
                    self.mc_constraint = extract_minecraft_constraints_fabric(fo)
            except: pass

        # 3. quilt.mod.json
        q_key = "quilt.mod.json" if "quilt.mod.json" in entries else "quilt_loader.json"
        if q_key in entries:
            try:
                qo = parse_json(entries[q_key])
                if isinstance(qo, dict):
                    md = qo.get("metadata") or {}
                    self.display_name = md.get("name") or self.display_name
                    self.description = md.get("description") or self.description
                    self.version = parse_version_string(md.get("version")) or self.version
                    self.mc_constraint = extract_minecraft_constraints_quilt(qo)
            except: pass

        # 4. mods.toml
        t_key = "META-INF/neoforge.mods.toml" if "META-INF/neoforge.mods.toml" in entries else "META-INF/mods.toml"
        if t_key in entries:
            try:
                # Use PCL-like line parsing
                toml_text = entries[t_key]
                data = simple_toml_parse(toml_text)
                mod_entry = None
                for sec in data:
                    if sec.get("__section__") in ("mods", "[[mods]]"):
                        mod_entry = sec
                        break
                if mod_entry:
                    self.display_name = mod_entry.get("displayName") or self.display_name
                    self.description = mod_entry.get("description") or self.description
                    self.version = parse_version_string(mod_entry.get("version")) or self.version
                
                # Extract constraints using PCL-aligned logic
                self.mc_constraint = extract_minecraft_constraints_forge_toml(toml_text)
            except: pass

        # 5. fml_cache_annotation.json
        if "META-INF/fml_cache_annotation.json" in entries:
            try:
                fj = parse_json(entries["META-INF/fml_cache_annotation.json"])
                if isinstance(fj, dict):
                    for _, v in fj.items():
                        ann = v.get("annotations", [])
                        for a in ann:
                            if a.get("name") == "Lnet/minecraftforge/fml/common/Mod;":
                                vals = a.get("values", {})
                                if "name" in vals: self.display_name = vals["name"].get("value")
                                if "version" in vals: self.version = parse_version_string(vals["version"].get("value"))
            except: pass

        # Fallback for version
        if (self.version or "").strip().lower() == "version":
            if "META-INF/MANIFEST.MF" in entries:
                self.version = manifest_impl_version(entries["META-INF/MANIFEST.MF"])
        
        if self.version and not ("." in self.version or "-" in self.version):
            self.version = None

    def fetch_network_info(self):
        """
        Attempts to fetch info from Modrinth using hash.
        Replicates PCL's McModDetailLoad logic (simplified).
        """
        h = self.get_modrinth_hash()
        if not h:
            return
        
        try:
            url = "https://api.modrinth.com/v2/version_files"
            data = json.dumps({"hashes": [h], "algorithm": "sha1"}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "PCL-Replication/1.0"})
            with urllib.request.urlopen(req) as res:
                body = res.read()
                resp_json = json.loads(body)
                if h in resp_json:
                    file_info = resp_json[h]
                    self.comp_file = CompFile(source="modrinth")
                    self.comp_file.id = file_info.get("project_id")
                    # Further API call would be needed to get Project info (Name, etc.), 
                    # but file info gives us game versions!
                    # "game_versions": ["1.16.5", "1.17"]
                    self.comp_file.game_versions = file_info.get("game_versions", [])
                    self.comp_file.loaders = file_info.get("loaders", [])
                    # Update local info if missing
                    # self.display_name = ... (requires project lookup)
        except Exception as e:
            # print(f"Network fetch failed: {e}")
            pass

def read_zip_text(zf, name):
    try:
        with zf.open(name) as f:
            b = f.read()
            try:
                return b.decode("utf-8")
            except UnicodeDecodeError:
                return b.decode("latin-1", errors="ignore")
    except KeyError:
        return None


def parse_json(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def simple_toml_parse(text):
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.strip().startswith("#"):
            continue
        if "#" in raw:
            raw = raw[: raw.index("#")]
        s = raw.strip(" \t")
        if s != "":
            lines.append(s)
    data = []
    current = {"__section__": ""}
    data.append(current)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("[[") and line.endswith("]]"):
            header = line.strip("[]")
            current = {"__section__": header}
            data.append(current)
        elif line.startswith("[") and line.endswith("]"):
            header = line.strip("[]")
            current = {"__section__": header}
            data.append(current)
        elif "=" in line:
            k, v = line.split("=", 1)
            k = k.rstrip(" \t")
            raw_v = v.lstrip(" \t")
            if raw_v.startswith('"""'):
                vals = [raw_v[3:]]
                while i + 1 < len(lines):
                    i += 1
                    l2 = lines[i]
                    if l2.endswith('"""'):
                        vals.append(l2[:-3])
                        break
                    else:
                        vals.append(l2)
                value = "\n".join(vals)
            elif raw_v.startswith("'''"):
                vals = [raw_v[3:]]
                while i + 1 < len(lines):
                    i += 1
                    l2 = lines[i]
                    if l2.endswith("'''"):
                        vals.append(l2[:-3])
                        break
                    else:
                        vals.append(l2)
                value = "\n".join(vals)
            elif raw_v.startswith('"') and raw_v.endswith('"'):
                value = raw_v.strip('"')
            elif raw_v.startswith("'") and raw_v.endswith("'"):
                value = raw_v.strip("'")
            elif raw_v.lower() in ("true", "false"):
                value = raw_v.lower() == "true"
            else:
                try:
                    if "." in raw_v:
                        value = float(raw_v)
                    else:
                        value = int(raw_v)
                except Exception:
                    value = raw_v
            current[k] = value
        i += 1
    return data


def parse_version_string(s):
    if s is None:
        return None
    return s.strip()


def manifest_impl_version(text):
    if not text:
        return None
    t = text.replace(" :", ":").replace(": ", ":")
    idx = t.find("Implementation-Version:")
    if idx == -1:
        return None
    part = t[idx + len("Implementation-Version:") :]
    end = part.find("\n")
    if end == -1:
        end = len(part)
    return part[:end].strip()


def detect_loader_from_entries(entries, fname):
    if entries.get("fabric.mod.json"):
        return "fabric"
    if entries.get("quilt.mod.json") or entries.get("quilt-loader.json") or entries.get("quilt_loader.json"):
        return "quilt"
    if entries.get("META-INF/mods.toml") or entries.get("META-INF/neoforge.mods.toml"):
        text = entries.get("META-INF/neoforge.mods.toml") or entries.get("META-INF/mods.toml")
        if text:
            mods_data = simple_toml_parse(text)
            for sec in mods_data:
                if sec.get("modLoader"):
                    ml = str(sec.get("modLoader")).lower()
                    if "neoforge" in ml:
                        return "neoforge"
                    return "forge"
        return "forge"
    if fname.lower().endswith(".litemod"):
        return "liteloder"
    return None


def extract_minecraft_constraints_fabric(obj):
    depends = obj.get("depends") or {}
    if isinstance(depends, dict):
        mc = depends.get("minecraft")
        if mc is None:
            return None
        if isinstance(mc, list):
            return " || ".join(str(x) for x in mc)
        return mc
    return None


def extract_minecraft_constraints_quilt(obj):
    loader = obj.get("quilt_loader") or {}
    deps = loader.get("depends")
    if not isinstance(deps, list):
        return None
    mc = []
    for d in deps:
        if isinstance(d, dict) and d.get("id") == "minecraft":
            v = d.get("version")
            if v:
                mc.append(v)
    if not mc:
        return None
    if len(mc) == 1:
        return mc[0]
    return " || ".join(mc)


def extract_minecraft_constraints_forge_toml(text):
    if not text:
        return None
    
    # Use structural parsing instead of heuristic regex which can leak into next sections
    try:
        data = simple_toml_parse(text)
        constraints = []
        
        for section in data:
            # Check for dependencies sections
            # Usually [[dependencies.modid]] or [dependencies.modid]
            # My simple parser puts section headers in __section__
            sec_name = section.get("__section__", "")
            if sec_name.startswith("dependencies."):
                if section.get("modId") == "minecraft":
                    vr = section.get("versionRange")
                    if vr:
                        constraints.append(vr)
        
        if not constraints:
            # Fallback: sometimes dependencies are just [[dependencies]] with modId inside
            if any(s.get("__section__") == "dependencies" for s in data):
                for section in data:
                    if section.get("__section__") == "dependencies":
                        if section.get("modId") == "minecraft":
                            vr = section.get("versionRange")
                            if vr:
                                constraints.append(vr)

        if not constraints:
            return None
            
        return " || ".join(constraints)
        
    except Exception:
        # Fallback to regex if parsing fails completely, but be stricter
        pass

    return None



def parse_range_expr(expr):
    expr = str(expr)
    parts = [p.strip() for p in re.split(r"\s*\|\|\s*", expr) if p.strip()]
    ranges = []
    for p in parts:
        m = re.match(r"^[\[\(]\s*([^,\s]*)\s*,\s*([^,\s]*)\s*[\]\)]$", p)
        if m:
            ranges.append(("interval", p[0], m.group(1), m.group(2), p[-1]))
            continue
        ranges.append(("token", p))
    return ranges


def version_tuple(v):
    try:
        segs = v.split(".")
        out = []
        for s in segs:
            s2 = re.sub(r"[^0-9].*$", "", s)
            if s2 == "":
                out.append(0)
            else:
                out.append(int(s2))
        while len(out) < 3:
            out.append(0)
        return tuple(out[:3])
    except Exception:
        return (0, 0, 0)


def compare_versions(a, b):
    ta = version_tuple(a)
    tb = version_tuple(b)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def match_token(ver, token):
    t = token.strip()
    if not t: return True
    if t == "*": return True # Wildcard support
    if t.startswith(">="):
        return compare_versions(ver, t[2:].strip()) >= 0
    if t.startswith("<="):
        return compare_versions(ver, t[2:].strip()) <= 0
    if t.startswith(">"):
        return compare_versions(ver, t[1:].strip()) > 0
    if t.startswith("<"):
        return compare_versions(ver, t[1:].strip()) < 0
    if t.startswith("="):
        t2 = t[1:].strip()
        return ver.startswith(t2)
    if "x" in t:
        prefix = t.split("x", 1)[0]
        return ver.startswith(prefix)
    return ver.startswith(t)


def match_interval(ver, left, lo, hi, right):
    if lo:
        c = compare_versions(ver, lo)
        if left == "[":
            if c < 0:
                return False
        else:
            if c <= 0:
                return False
    if hi:
        c = compare_versions(ver, hi)
        if right == "]":
            if c > 0:
                return False
        else:
            if c >= 0:
                return False
    return True


def is_version_supported(ver, constraint):
    if constraint is None:
        return None # Unknown
    rs = parse_range_expr(str(constraint))
    if not rs:
        return None
    ok_any = False
    for r in rs:
        if r[0] == "interval":
            if match_interval(ver, r[1], r[2], r[3], r[4]):
                ok_any = True
                break
        else:
            if match_token(ver, r[1]):
                ok_any = True
                break
    return ok_any


def pcl_is_compatible(mod, target_version):
    # 1. Network Fallback
    if mod.comp_file and mod.comp_file.game_versions:
        # Check against list
        if target_version in mod.comp_file.game_versions:
            return True
        # Check via Drop ID
        t_drop = pcl_version_to_drop(target_version)
        if t_drop > 0:
            for v in mod.comp_file.game_versions:
                if pcl_version_to_drop(v) == t_drop:
                    return True
        return False

    # 2. Local Constraint
    if mod.mc_constraint:
        return is_version_supported(target_version, mod.mc_constraint)
    
    # 3. No info
    return None # Unknown

# --- GUI Class ---

class ModCheckGUI:
    def __init__(self, root):
        self.root = root
        self.root.geometry("950x600")

        # Styles
        style = ttk.Style()
        style.theme_use('clam')

        # Variables
        self.mods_dir_var = tk.StringVar()
        self.mc_version_var = tk.StringVar(value="1.20.1")
        self.loader_var = tk.StringVar(value="Any")
        self.network_check_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value=T("msg_done"))
        self.lang_var = tk.StringVar(value=LANG_NAMES.get(CURRENT_LANG, "English"))

        self.main_frame = None
        self.build_ui()

    def build_ui(self):
        if self.main_frame:
            self.main_frame.destroy()
        
        self.root.title(T("title"))
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Top Bar (Language)
        top_bar = ttk.Frame(self.main_frame)
        top_bar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(top_bar, text=T("lang_select")).pack(side=tk.LEFT)
        lang_cb = ttk.Combobox(top_bar, textvariable=self.lang_var, values=list(LANG_NAMES.values()), state="readonly", width=15)
        lang_cb.pack(side=tk.LEFT, padx=5)
        lang_cb.bind("<<ComboboxSelected>>", self.on_lang_change)

        # Controls
        controls_frame = ttk.LabelFrame(self.main_frame, text=T("title"), padding="10")
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Mods Directory
        ttk.Label(controls_frame, text=T("mod_dir")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(controls_frame, textvariable=self.mods_dir_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(controls_frame, text=T("browse"), command=self.browse_dir).grid(row=0, column=2, padx=5, pady=5)

        # MC Version
        ttk.Label(controls_frame, text=T("mc_version")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(controls_frame, textvariable=self.mc_version_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Loader
        ttk.Label(controls_frame, text=T("loader")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        loader_cb = ttk.Combobox(controls_frame, textvariable=self.loader_var, values=["Any", "Forge", "NeoForge", "Fabric", "Quilt", "LiteLoader"], state="readonly")
        loader_cb.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Network Check
        ttk.Checkbutton(controls_frame, text=T("network_check"), variable=self.network_check_var).grid(row=2, column=2, padx=5, pady=5)

        # Check Button
        ttk.Button(controls_frame, text=T("start_check"), command=self.start_check).grid(row=3, column=0, columnspan=3, pady=10)

        # Results Area
        results_frame = ttk.LabelFrame(self.main_frame, text="Results", padding="5")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("file", "name", "version", "loader", "constraint", "drop", "status")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        self.tree.heading("file", text=T("col_filename"))
        self.tree.heading("name", text=T("col_modname"))
        self.tree.heading("version", text=T("col_version"))
        self.tree.heading("loader", text=T("col_loader"))
        self.tree.heading("constraint", text=T("col_constraint"))
        self.tree.heading("drop", text=T("col_drop"))
        self.tree.heading("status", text=T("col_status"))
        
        self.tree.column("file", width=200)
        self.tree.column("name", width=150)
        self.tree.column("version", width=80)
        self.tree.column("loader", width=80)
        self.tree.column("constraint", width=120)
        self.tree.column("drop", width=60)
        self.tree.column("status", width=80)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status Bar
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Show initial drop
        self.update_drop_display()
        self.mc_version_var.trace("w", lambda *args: self.update_drop_display())

    def on_lang_change(self, event):
        global CURRENT_LANG
        selected_name = self.lang_var.get()
        for code, name in LANG_NAMES.items():
            if name == selected_name:
                CURRENT_LANG = code
                self.build_ui()
                break

    def update_drop_display(self):
        ver = self.mc_version_var.get()
        drop = pcl_version_to_drop(ver)
        self.status_var.set(f"{T('msg_done')} - Target Drop: {drop}")

    def browse_dir(self):
        d = filedialog.askdirectory(title=T("msg_select_dir"))
        if d:
            self.mods_dir_var.set(d)

    def start_check(self):
        mods_dir = self.mods_dir_var.get()
        mc_ver = self.mc_version_var.get()
        loader = self.loader_var.get()
        use_net = self.network_check_var.get()

        if not mods_dir or not os.path.isdir(mods_dir):
            messagebox.showerror("Error", T("msg_dir_not_exist"))
            return
        if not mc_ver:
            messagebox.showerror("Error", "Please enter Minecraft version.")
            return

        # Clear previous results
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.status_var.set(T("msg_checking"))
        
        # Run in thread
        threading.Thread(target=self.run_check, args=(mods_dir, mc_ver, loader, use_net), daemon=True).start()

    def run_check(self, mods_dir, mc_ver, loader_filter, use_net):
        try:
            files = sorted(os.listdir(mods_dir))
            for f in files:
                path = os.path.join(mods_dir, f)
                if not os.path.isfile(path):
                    continue
                
                # Use McMod class
                mod = McMod(path)
                
                # Basic validity check (is it a mod file?)
                valid_exts = (".jar", ".zip", ".litemod", ".jar.disabled", ".zip.disabled", ".litemod.disabled", ".jar.old", ".zip.old", ".litemod.old")
                if not any(f.lower().endswith(ext) for ext in valid_exts):
                    continue

                if use_net:
                    self.root.after(0, lambda: self.status_var.set(T("net_check_console").format(file=f)))
                    mod.fetch_network_info()
                
                # Check compatibility
                is_compat = pcl_is_compatible(mod, mc_ver)
                
                # Determine status string/color
                status_str = T("status_unknown")
                tags = ()
                if is_compat is True:
                    status_str = T("status_compat")
                    tags = ("ok",)
                elif is_compat is False:
                    status_str = T("status_incompat")
                    tags = ("fail",)
                
                # Filter by loader
                mod_loaders = mod.loaders
                if not mod_loaders:
                    mod_loaders_str = "Unknown"
                else:
                    mod_loaders_str = ", ".join(sorted(mod_loaders))

                if loader_filter != "Any":
                    norm_filter = loader_filter.lower()
                    if norm_filter not in mod_loaders:
                        # Logic: if specific loader requested and mod doesn't have it -> Mismatch?
                        # Or just show it? 
                        pass
                
                # Prepare values
                vals = (
                    f,
                    mod.display_name or "",
                    mod.version or "",
                    mod_loaders_str,
                    mod.mc_constraint or "",
                    pcl_version_to_drop(mc_ver),
                    status_str
                )
                
                self.root.after(0, lambda v=vals, t=tags: self.tree.insert("", "end", values=v, tags=t))
            
            self.root.after(0, lambda: self.status_var.set(T("msg_done")))
            self.root.after(0, self.apply_tags)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def apply_tags(self):
        self.tree.tag_configure("ok", foreground="green")
        self.tree.tag_configure("fail", foreground="red")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # CLI Mode
        parser = argparse.ArgumentParser(prog="mod_support_check", description=T("cli_desc"), add_help=True)
        parser.add_argument("--mc-version", required=True, help=T("cli_ver_help"))
        parser.add_argument("--loader", required=True, choices=["forge", "neoforge", "fabric", "quilt", "liteloader", "any"], help=T("cli_loader_help"))
        parser.add_argument("--mods-dir", required=True, help=T("cli_dir_help"))
        parser.add_argument("--network", action="store_true", help=T("cli_net_help"))
        args = parser.parse_args()
        
        mc_version = args.mc_version.strip()
        loader_filter = args.loader.lower()
        mods_dir = args.mods_dir
        use_net = args.network
        
        if not os.path.isdir(mods_dir):
            print(T("msg_dir_not_exist"))
            sys.exit(1)
            
        files = sorted(os.listdir(mods_dir))
        print(T("checking_console").format(dir=mods_dir, ver=mc_version, ldr=loader_filter))
        
        for f in files:
            path = os.path.join(mods_dir, f)
            if not os.path.isfile(path):
                continue
            
            # Use McMod class
            mod = McMod(path)
            
            valid_exts = (".jar", ".zip", ".litemod", ".jar.disabled", ".zip.disabled", ".litemod.disabled", ".jar.old", ".zip.old", ".litemod.old")
            if not any(f.lower().endswith(ext) for ext in valid_exts):
                continue

            if use_net:
                print(T("net_check_console").format(file=f), end="\r")
                mod.fetch_network_info()
            
            # Check compatibility
            is_compat = pcl_is_compatible(mod, mc_version)
            
            status_str = T("status_unknown")
            if is_compat is True:
                status_str = T("status_compat")
            elif is_compat is False:
                status_str = T("status_incompat")
            
            mod_loaders = mod.loaders
            mod_loaders_str = ", ".join(sorted(mod_loaders)) if mod_loaders else "Unknown"
            
            if loader_filter != "any" and mod_loaders:
                if loader_filter not in mod_loaders:
                     status_str += f" ({T('status_loader_mismatch')})"

            print(
                "{} | Ver: {} | Loader: {} | Constraint: {} | Drop: {} | {}".format(
                    f,
                    mod.version or "?",
                    mod_loaders_str,
                    mod.mc_constraint or "?",
                    pcl_version_to_drop(mc_version),
                    status_str
                )
            )

    else:
        # GUI Mode
        root = tk.Tk()
        app = ModCheckGUI(root)
        root.mainloop()
