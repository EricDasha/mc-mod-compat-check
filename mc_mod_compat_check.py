from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
import locale
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional, Callable
from threading import Thread

# --- Constants ---
MODRINTH_VERSION_FILE_SHA1_URL = "https://api.modrinth.com/v2/version_file/sha1/"
DEFAULT_USER_AGENT = "mc-mod-compat-check/2.0 (local script)"
CACHE_FILE_NAME = ".mod_compat_cache.json"
CONFIG_FILE_NAME = "mod_compat_config.json"

LOADER_COMPAT = {
    "fabric": {"fabric", "quilt"},
    "quilt": {"quilt", "fabric"},
    "forge": {"forge", "neoforge"},
    "neoforge": {"neoforge", "forge"},
}

KNOWN_LOADERS = {"forge", "fabric", "neoforge", "quilt", "liteloader", "rift"}
MC_VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")

# --- i18n ---
LANGUAGES = {
    "en": "English",
    "zh_CN": "简体中文",
    "zh_TW": "繁體中文",
    "ja": "日本語",
    "ko": "한국어",
}

CURSEFORGE_API_URL = "https://api.curseforge.com/v1"

# --- MurmurHash2 for CurseForge ---
def murmurhash2(data: bytes, seed: int = 1) -> int:
    """
    Pure Python implementation of MurmurHash2 (32-bit) used by CurseForge.
    CurseForge implementation details:
    - Seed is 1.
    - Whitespace bytes (9, 10, 13, 32) are STRIPPED before hashing.
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

# --- CurseForge API Client ---
class CurseForgeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_fingerprint_matches(self, fingerprints: list[int]) -> dict[int, dict]:
        if not self.api_key or not fingerprints:
            return {}
            
        url = f"{CURSEFORGE_API_URL}/fingerprints"
        results = {}
        
        # CF allows batching.
        chunk_size = 50 
        for i in range(0, len(fingerprints), chunk_size):
            chunk = fingerprints[i:i+chunk_size]
            data = {"fingerprints": chunk}
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            try:
                req = urllib.request.Request(
                    url, 
                    data=json.dumps(data).encode("utf-8"), 
                    headers=headers, 
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        body = json.loads(resp.read().decode("utf-8"))
                        matches = body.get("data", {}).get("exactMatches", [])
                        for m in matches:
                            # The "id" in exactMatches IS the fingerprint.
                            fid = m.get("id")
                            if fid:
                                results[fid] = m
            except Exception:
                pass
        return results
    
    def get_fingerprint_match(self, file_hash: int) -> Optional[dict]:
        res = self.get_fingerprint_matches([file_hash])
        return res.get(file_hash)

    def check_connection(self) -> bool:
        if not self.api_key:
            return False
        url = f"{CURSEFORGE_API_URL}/games"
        headers = {"x-api-key": self.api_key}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False


class ModrinthClient:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.user_agent = user_agent
        self.base_url = "https://api.modrinth.com/v2"

    def get_versions_by_hashes(self, hashes: list[str], timeout_s: float = 10.0) -> dict[str, dict]:
        """
        Batch query Modrinth for version files.
        Returns a dict mapping sha1 -> version_data
        """
        if not hashes:
            return {}
        
        url = f"{self.base_url}/version_files"
        results = {}
        
        # Modrinth allows batching.
        chunk_size = 50
        for i in range(0, len(hashes), chunk_size):
            chunk = hashes[i:i+chunk_size]
            try:
                data = json.dumps({"hashes": chunk, "algorithm": "sha1"}).encode("utf-8")
                req = urllib.request.Request(
                    url, 
                    data=data, 
                    headers={"User-Agent": self.user_agent, "Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    if resp.status == 200:
                        body = json.loads(resp.read().decode("utf-8"))
                        # Body is dict: { "sha1": version_object, ... }
                        results.update(body)
            except Exception:
                pass
                
        return results

    def check_connection(self) -> bool:
        try:
            # Check Modrinth root API
            req = urllib.request.Request(
                self.base_url, 
                headers={"User-Agent": self.user_agent}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

TRANSLATIONS = {
    "en": {
        "window_title": "MC Mod Compatibility Checker",
        "select_folder": "Mods Folder:",
        "mc_version": "MC Version:",
        "loader": "Loader:",
        "start_check": "Start Check",
        "status": "Status",
        "file": "File",
        "source": "Source",
        "reason": "Reason",
        "mod_name": "Mod Name",
        "ok": "OK",
        "fail": "FAIL",
        "wrong_mc": "Wrong MC",
        "wrong_loader": "Wrong Loader",
        "not_found": "Not Found",
        "network_error": "Network Error",
        "unknown": "Unknown",
        "skipped": "Skipped",
        "unknown_loader": "Unknown Loader",
        "browse": "Browse",
        "all_files": "All Files",
        "scanning": "Scanning: {}",
        "done": "Done! Checked {} files.",
        "error": "Error",
        "select_dir_msg": "Please select a mods directory.",
        "enter_mc_msg": "Please enter a Minecraft version.",
        "stop": "Stop",
        "stopped": "Stopped.",
        "threads": "Threads:",
        "relaxed": "Relaxed Mode",
        "no_cache": "No Cache",
        "language": "Language:",
        "tooltip_browse": "Select the directory containing .jar mod files.",
        "tooltip_mc_version": "The target Minecraft version (e.g., 1.20.1).",
        "tooltip_loader": "Expected mod loader. If specified, warns if mod doesn't support it.",
        "tooltip_relaxed": "Match major versions (e.g. 1.20 matches 1.20.1). Useful for mods with loose versioning.",
        "tooltip_no_cache": "Ignore local cache and force fresh network checks.",
        "tooltip_threads": "Number of concurrent checks. Too high may cause rate limiting.",
        "tooltip_lang": "Switch interface language.",
        "tooltip_start": "Start the compatibility check process.",
        "tooltip_stop": "Stop the current check process.",
        "cf_api_key": "CurseForge API Key:",
        "tooltip_cf_key": "Optional. Enter your CurseForge Core API Key to enable CurseForge checks.",
        "get_key": "Get Key",
        "tutorials": "Tutorials",
        "test_api": "Test API Connections",
        "api_status": "API Status",
        "api_ok": "OK",
        "api_fail": "FAIL",
        "tools": "Tools",
    },
    "zh_CN": {
        "window_title": "MC Mod 兼容性检查器",
        "select_folder": "Mods 目录:",
        "mc_version": "MC 版本:",
        "loader": "加载器:",
        "start_check": "开始检查",
        "status": "状态",
        "file": "文件",
        "source": "来源",
        "reason": "原因",
        "mod_name": "Mod 名称",
        "ok": "兼容",
        "fail": "不兼容",
        "wrong_mc": "版本不符",
        "wrong_loader": "加载器不符",
        "not_found": "未收录",
        "network_error": "网络错误",
        "unknown": "未知",
        "skipped": "跳过",
        "unknown_loader": "加载器未知",
        "browse": "浏览...",
        "all_files": "所有文件",
        "scanning": "正在扫描: {}",
        "done": "完成！共检查 {} 个文件。",
        "error": "错误",
        "select_dir_msg": "请选择 mods 目录。",
        "enter_mc_msg": "请输入 Minecraft 版本。",
        "stop": "停止",
        "stopped": "已停止。",
        "threads": "并发数:",
        "relaxed": "宽松模式",
        "no_cache": "禁用缓存",
        "language": "语言:",
        "tooltip_browse": "选择包含 .jar 模组文件的目录。",
        "tooltip_mc_version": "目标 Minecraft 版本（例如 1.20.1）。",
        "tooltip_loader": "预期的模组加载器。如果指定，将检查模组是否支持该加载器。",
        "tooltip_relaxed": "宽松匹配主版本（如 1.20 匹配 1.20.1）。适用于版本号标注不严谨的模组。",
        "tooltip_no_cache": "忽略本地缓存，强制从网络重新检查。",
        "tooltip_threads": "并发检查数量。设置过高可能会触发 API 速率限制。",
        "tooltip_lang": "切换界面语言。",
        "tooltip_start": "开始兼容性检查。",
        "tooltip_stop": "停止当前检查。",
        "cf_api_key": "CF API 密钥:",
        "tooltip_cf_key": "可选。输入 CurseForge Core API Key 以启用 CurseForge 检查。",
        "get_key": "获取密钥",
        "tutorials": "教程",
        "test_api": "测试 API 连接",
        "api_status": "API 状态",
        "api_ok": "正常",
        "api_fail": "失败",
        "tools": "工具",
    },
    "zh_TW": {
        "window_title": "MC Mod 相容性檢查器",
        "select_folder": "Mods 目錄:",
        "mc_version": "MC 版本:",
        "loader": "加載器:",
        "start_check": "開始檢查",
        "status": "狀態",
        "file": "文件",
        "source": "來源",
        "reason": "原因",
        "mod_name": "Mod 名稱",
        "ok": "相容",
        "fail": "不相容",
        "wrong_mc": "版本不符",
        "wrong_loader": "加載器不符",
        "not_found": "未收錄",
        "network_error": "網絡錯誤",
        "unknown": "未知",
        "skipped": "跳過",
        "unknown_loader": "加載器未知",
        "browse": "瀏覽...",
        "all_files": "所有文件",
        "scanning": "正在掃描: {}",
        "done": "完成！共檢查 {} 個文件。",
        "error": "錯誤",
        "select_dir_msg": "請選擇 mods 目錄。",
        "enter_mc_msg": "請輸入 Minecraft 版本。",
        "stop": "停止",
        "stopped": "已停止。",
        "threads": "並發數:",
        "relaxed": "寬鬆模式",
        "no_cache": "禁用緩存",
        "language": "語言:",
        "tooltip_browse": "選擇包含 .jar 模組文件的目錄。",
        "tooltip_mc_version": "目標 Minecraft 版本（例如 1.20.1）。",
        "tooltip_loader": "預期的模組加載器。如果指定，將檢查模組是否支持該加載器。",
        "tooltip_relaxed": "寬鬆匹配主版本（如 1.20 匹配 1.20.1）。適用於版本號標註不嚴謹的模組。",
        "tooltip_no_cache": "忽略本地緩存，強制從網絡重新檢查。",
        "tooltip_threads": "並發檢查數量。設置過高可能會觸發 API 速率限制。",
        "tooltip_lang": "切換界面語言。",
        "tooltip_start": "開始相容性檢查。",
        "tooltip_stop": "停止當前檢查。",
        "cf_api_key": "CF API 密鑰:",
        "tooltip_cf_key": "可選。輸入 CurseForge Core API Key 以啟用 CurseForge 檢查。",
        "get_key": "獲取密鑰",
        "tutorials": "教程",
    },
    "ja": {
        "window_title": "MC Mod 互換性チェッカー",
        "select_folder": "Mods フォルダ:",
        "mc_version": "MC バージョン:",
        "loader": "ローダー:",
        "start_check": "チェック開始",
        "status": "状態",
        "file": "ファイル",
        "source": "ソース",
        "reason": "理由",
        "mod_name": "Mod名",
        "ok": "OK",
        "fail": "失敗",
        "wrong_mc": "バージョン不一致",
        "wrong_loader": "ローダー不一致",
        "not_found": "見つかりません",
        "network_error": "ネットワークエラー",
        "unknown": "不明",
        "skipped": "スキップ",
        "unknown_loader": "ローダー不明",
        "browse": "参照...",
        "all_files": "すべてのファイル",
        "scanning": "スキャン中: {}",
        "done": "完了！ {} 個のファイルをチェックしました。",
        "error": "エラー",
        "select_dir_msg": "Mods ディレクトリを選択してください。",
        "enter_mc_msg": "Minecraft バージョンを入力してください。",
        "stop": "停止",
        "stopped": "停止しました。",
        "threads": "スレッド数:",
        "relaxed": "緩和モード",
        "no_cache": "キャッシュ無効",
        "language": "言語:",
        "tooltip_browse": ".jar Modファイルが含まれるディレクトリを選択します。",
        "tooltip_mc_version": "ターゲットMinecraftバージョン（例：1.20.1）。",
        "tooltip_loader": "期待されるModローダー。指定された場合、サポートされていないModに警告します。",
        "tooltip_relaxed": "メジャーバージョンを一致させます（例：1.20は1.20.1に一致）。バージョン管理が緩いModに役立ちます。",
        "tooltip_no_cache": "ローカルキャッシュを無視し、強制的にネットワークチェックを行います。",
        "tooltip_threads": "同時チェック数。高すぎるとレート制限が発生する可能性があります。",
        "tooltip_lang": "インターフェース言語を切り替えます。",
        "tooltip_start": "互換性チェックを開始します。",
        "tooltip_stop": "現在のチェックを停止します。",
        "cf_api_key": "CF APIキー:",
        "tooltip_cf_key": "オプション。CurseForge Core APIキーを入力してCFチェックを有効にします。",
        "get_key": "キーを取得",
        "tutorials": "チュートリアル",
    },
    "ko": {
        "window_title": "MC Mod 호환성 검사기",
        "select_folder": "Mods 폴더:",
        "mc_version": "MC 버전:",
        "loader": "로더:",
        "start_check": "검사 시작",
        "status": "상태",
        "file": "파일",
        "source": "출처",
        "reason": "이유",
        "mod_name": "Mod 이름",
        "ok": "호환됨",
        "fail": "호환되지 않음",
        "wrong_mc": "버전 불일치",
        "wrong_loader": "로더 불일치",
        "not_found": "찾을 수 없음",
        "network_error": "네트워크 오류",
        "unknown": "알 수 없음",
        "skipped": "건너뜀",
        "unknown_loader": "로더 알 수 없음",
        "browse": "찾아보기...",
        "all_files": "모든 파일",
        "scanning": "스캔 중: {}",
        "done": "완료! {} 개의 파일을 검사했습니다.",
        "error": "오류",
        "select_dir_msg": "Mods 디렉토리를 선택하십시오.",
        "enter_mc_msg": "Minecraft 버전을 입력하십시오.",
        "stop": "중지",
        "stopped": "중지됨.",
        "threads": "스레드:",
        "relaxed": "관대 모드",
        "no_cache": "캐시 사용 안 함",
        "language": "언어:",
        "tooltip_browse": ".jar 모드 파일이 포함된 디렉토리를 선택하십시오.",
        "tooltip_mc_version": "대상 Minecraft 버전 (예: 1.20.1).",
        "tooltip_loader": "예상 모드 로더. 지정된 경우 모드가 지원하지 않으면 경고합니다.",
        "tooltip_relaxed": "메이저 버전을 일치시킵니다 (예: 1.20은 1.20.1과 일치). 버전 관리가 느슨한 모드에 유용합니다.",
        "tooltip_no_cache": "로컬 캐시를 무시하고 강제로 네트워크 검사를 수행합니다.",
        "tooltip_threads": "동시 검사 수. 너무 높으면 속도 제한이 발생할 수 있습니다.",
        "tooltip_lang": "인터페이스 언어를 전환합니다.",
        "tooltip_start": "호환성 검사를 시작합니다.",
        "tooltip_stop": "현재 검사를 중지합니다.",
        "cf_api_key": "CF API 키:",
        "tooltip_cf_key": "선택 사항. CurseForge Core API 키를 입력하여 CF 검사를 활성화하십시오.",
        "get_key": "키 받기",
        "tutorials": "튜토리얼",
    },
}

CURRENT_LANG = "en"

def detect_language():
    try:
        lang_code, _ = locale.getdefaultlocale()
        if lang_code:
            if lang_code.startswith("zh_CN"): return "zh_CN"
            if lang_code.startswith("zh_TW") or lang_code.startswith("zh_HK"): return "zh_TW"
            if lang_code.startswith("ja"): return "ja"
            if lang_code.startswith("ko"): return "ko"
    except:
        pass
    return "en"

def tr(key: str) -> str:
    return TRANSLATIONS.get(CURRENT_LANG, TRANSLATIONS["en"]).get(key, key)



class CheckStatus(str, Enum):
    OK = "OK"
    FAIL = "FAIL"
    WRONG_MC = "WRONG_MC"
    WRONG_LOADER = "WRONG_LOADER"
    NOT_FOUND = "NOT_FOUND"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"
    UNKNOWN_LOADER = "UNKNOWN_LOADER"


@dataclass(frozen=True)
class ModCheckResult:
    file_name: str
    file_path: str
    status: CheckStatus
    reason: str
    source: str
    mod_name: Optional[str] = None
    mod_version: Optional[str] = None
    loaders: Optional[list[str]] = None
    supported_game_versions: Optional[list[str]] = None
    url: Optional[str] = None
    timestamp: Optional[float] = None


class ConfigManager:
    def __init__(self):
        self.config_path = os.path.join(os.getcwd(), CONFIG_FILE_NAME)
        self.data = {
            "cf_api_key": "",
            "language": "en",
            "threads": 4,
            "relaxed_mc": False,
            "no_cache": False,
            "last_dir": os.getcwd(),
            "last_mc": "1.20.1",
            "last_loader": "",
            "tutorials": [
                {"title": "Get CurseForge API Key", "url": "https://console.curseforge.com/"},
                {"title": "Modrinth API Docs", "url": "https://docs.modrinth.com/"}
            ]
        }
        self.load()
        if not os.path.exists(self.config_path):
            self.save()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Update only existing keys or add new ones? 
                    # Let's simple update
                    self.data.update(loaded)
            except Exception:
                pass

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


class CacheManager:
    def __init__(self, cache_dir: str):
        self.cache_path = os.path.join(cache_dir, CACHE_FILE_NAME)
        self.data: dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.data = {}

    def get(self, sha1: str) -> Optional[dict]:
        return self.data.get(sha1)

    def set(self, sha1: str, data: dict):
        self.data[sha1] = data

    def save(self):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=None)
        except OSError:
            pass


def iter_jar_files(root_dir: str) -> Iterable[str]:
    for entry in os.scandir(root_dir):
        if not entry.is_file():
            continue
        if entry.name.lower().endswith(".jar"):
            yield entry.path


def sha1_file(path: str) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def http_get_json(url: str, user_agent: str, timeout_s: float) -> tuple[int, Optional[dict[str, Any]]]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read()
            if not body:
                return status, None
            return status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
            if body:
                return e.code, json.loads(body.decode("utf-8"))
        except Exception:
            pass
        return e.code, None
    except urllib.error.URLError:
        return 0, None





_VERSION_SPLIT_RE = re.compile(r"[.\-_+]")


def parse_version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for token in _VERSION_SPLIT_RE.split(version.strip()):
        if not token:
            continue
        m = re.match(r"^(\d+)", token)
        if not m:
            break
        parts.append(int(m.group(1)))
    return tuple(parts)


def cmp_versions(a: str, b: str) -> int:
    ta = parse_version_tuple(a)
    tb = parse_version_tuple(b)
    max_len = max(len(ta), len(tb))
    ta = ta + (0,) * (max_len - len(ta))
    tb = tb + (0,) * (max_len - len(tb))
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def matches_wildcard(target: str, pattern: str) -> bool:
    if pattern.endswith(".x"):
        prefix = pattern[:-2]
        return target == prefix or target.startswith(prefix + ".")
    return target == pattern


def eval_simple_constraints(target: str, constraint: str) -> Optional[bool]:
    c = constraint.strip()
    if not c:
        return None

    if "||" in c:
        parts = [p.strip() for p in c.split("||") if p.strip()]
        results = [eval_simple_constraints(target, p) for p in parts]
        known = [r for r in results if r is not None]
        if not known:
            return None
        return any(known)

    m = re.match(r"^(>=|<=|>|<|=)\s*(.+)$", c)
    if m:
        op, v = m.group(1), m.group(2).strip()
        if v.endswith(".x"):
            if op in (">=", ">", "<=", "<"):
                return None
            return matches_wildcard(target, v)
        comp = cmp_versions(target, v)
        if op == ">=":
            return comp >= 0
        if op == "<=":
            return comp <= 0
        if op == ">":
            return comp > 0
        if op == "<":
            return comp < 0
        if op == "=":
            return comp == 0
        return None

    if re.search(r"\s", c):
        tokens = [t for t in c.split() if t]
        results: list[bool] = []
        for t in tokens:
            r = eval_simple_constraints(target, t)
            if r is None:
                return None
            results.append(r)
        return all(results)

    if c.endswith(".x"):
        return matches_wildcard(target, c)

    if c.startswith("^") or c.startswith("~"):
        base = c[1:].strip()
        if not base:
            return None
        return cmp_versions(target, base) >= 0

    if c.startswith("[") or c.startswith("("):
        return eval_maven_range(target, c)

    return matches_wildcard(target, c)


def eval_maven_range(target: str, expr: str) -> Optional[bool]:
    s = expr.strip()
    if not s:
        return None
    if not (s.startswith("[") or s.startswith("(")) or not (s.endswith("]") or s.endswith(")")):
        return None

    lower_inclusive = s[0] == "["
    upper_inclusive = s[-1] == "]"
    inner = s[1:-1].strip()
    if not inner:
        return None

    if "," not in inner:
        v = inner.strip()
        return cmp_versions(target, v) == 0

    lower_str, upper_str = [p.strip() for p in inner.split(",", 1)]
    if lower_str:
        comp = cmp_versions(target, lower_str)
        if lower_inclusive:
            if comp < 0:
                return False
        else:
            if comp <= 0:
                return False
    if upper_str:
        comp = cmp_versions(target, upper_str)
        if upper_inclusive:
            if comp > 0:
                return False
        else:
            if comp >= 0:
                return False
    return True


def read_zip_text(z: zipfile.ZipFile, path: str) -> Optional[str]:
    try:
        data = z.read(path)
    except KeyError:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None


def try_local_metadata_check(
    jar_path: str, 
    target_mc: str, 
    expected_loader: Optional[str] = None, 
    relaxed_mc: bool = False
) -> Optional[ModCheckResult]:
    """
    尝试从 jar 内的元数据文件判断兼容性。
    支持: fabric.mod.json, mods.toml, quilt.mod.json, neoforge.mods.toml
    """
    file_name = os.path.basename(jar_path)
    
    try:
        with zipfile.ZipFile(jar_path) as z:
            # 1. Fabric
            fabric_json = read_zip_text(z, "fabric.mod.json")
            if fabric_json:
                try:
                    meta = json.loads(fabric_json)
                except json.JSONDecodeError:
                    pass
                else:
                    mod_name = meta.get("name") or meta.get("id")
                    mod_version = meta.get("version")
                    
                    # Check Loader
                    if expected_loader and expected_loader.lower() not in ("fabric", "quilt"):
                        return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_LOADER, "is_fabric", "local", mod_name, mod_version)

                    # Check MC
                    depends = meta.get("depends")
                    if isinstance(depends, dict):
                        mc_dep = depends.get("minecraft")
                        if mc_dep:
                            # Normalize to list
                            if isinstance(mc_dep, str):
                                mc_dep = [mc_dep]
                            elif isinstance(mc_dep, dict):
                                mc_dep = [mc_dep.get("version")] if mc_dep.get("version") else []
                            
                            if isinstance(mc_dep, list):
                                constraints = []
                                for item in mc_dep:
                                    if isinstance(item, str): constraints.append(item)
                                    elif isinstance(item, dict):
                                        v = item.get("version")
                                        if v: constraints.append(v)
                                
                                status = CheckStatus.UNKNOWN
                                msg = f"fabric: {constraints}"

                                if len(constraints) == 1:
                                    # Single string -> Strict check
                                    c = constraints[0]
                                    if relaxed_mc:
                                        if c == "*" or eval_simple_constraints(target_mc, c):
                                            status = CheckStatus.OK
                                        # Simple relaxed check for "1.20" vs "1.20.1" if constraint is specific version
                                        elif not any(x in c for x in ['>', '<', '=', '~', '^', ' ']):
                                             if mc_version_compatible(target_mc, [c], relaxed=True):
                                                 status = CheckStatus.OK
                                             else:
                                                 status = CheckStatus.WRONG_MC
                                        else:
                                             status = CheckStatus.WRONG_MC
                                    else:
                                        if eval_simple_constraints(target_mc, c):
                                            status = CheckStatus.OK
                                        else:
                                            status = CheckStatus.WRONG_MC
                                
                                elif len(constraints) > 1:
                                    # List -> Check if it looks like a list of versions (OR) or ranges (AND)
                                    # User feedback: "If list, prioritize OR, unless explicit range syntax"
                                    
                                    has_range_syntax = False
                                    for c in constraints:
                                        if any(x in c for x in ['>', '<', '=', '~', '^', ' ']) or c == '*':
                                            has_range_syntax = True
                                            break
                                    
                                    if has_range_syntax:
                                        # Likely a split range ["=1.19", "!=1.19.2"] or [">=1.19", "<1.21"] -> AND
                                        if all(eval_simple_constraints(target_mc, c) for c in constraints):
                                            status = CheckStatus.OK
                                        else:
                                            status = CheckStatus.WRONG_MC
                                    else:
                                        # Likely discrete versions ["1.19", "1.19.1"] -> OR
                                        matched_any = False
                                        for c in constraints:
                                            if relaxed_mc:
                                                if mc_version_compatible(target_mc, [c], relaxed=True):
                                                    matched_any = True
                                                    break
                                            else:
                                                if eval_simple_constraints(target_mc, c):
                                                    matched_any = True
                                                    break
                                        
                                        if matched_any:
                                            status = CheckStatus.OK
                                        else:
                                            status = CheckStatus.WRONG_MC
                                    
                                    # Avoid UNKNOWN if we decided logic
                                    msg = f"fabric list: {constraints}"

                                if status != CheckStatus.UNKNOWN:
                                    return ModCheckResult(file_name, jar_path, status, msg, "local", mod_name, mod_version)

            # 2. Forge (mods.toml)
            mods_toml = read_zip_text(z, "META-INF/mods.toml")
            if mods_toml:
                mod_name = None
                mod_version = None
                m_name = re.search(r'displayName\s*=\s*"(.*?)"', mods_toml)
                if m_name: mod_name = m_name.group(1)
                m_ver = re.search(r'version\s*=\s*"(.*?)"', mods_toml)
                if m_ver: mod_version = m_ver.group(1)

                if expected_loader and expected_loader.lower() not in ("forge", "neoforge"):
                     return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_LOADER, "is_forge", "local", mod_name, mod_version)

                mc_range = extract_minecraft_version_range_from_toml(mods_toml)
                if mc_range:
                    if eval_simple_constraints(target_mc, mc_range):
                         return ModCheckResult(file_name, jar_path, CheckStatus.OK, f"forge: {mc_range}", "local", mod_name, mod_version)
                    else:
                         return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_MC, f"forge: {mc_range}", "local", mod_name, mod_version)

            # 3. Neoforge (neoforge.mods.toml)
            neo_toml = read_zip_text(z, "META-INF/neoforge.mods.toml")
            if neo_toml:
                if expected_loader and expected_loader.lower() not in ("neoforge", "forge"):
                     return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_LOADER, "is_neoforge", "local")
                
                mc_range = extract_minecraft_version_range_from_toml(neo_toml)
                if mc_range:
                    if eval_simple_constraints(target_mc, mc_range):
                         return ModCheckResult(file_name, jar_path, CheckStatus.OK, f"neoforge: {mc_range}", "local")
                    else:
                         return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_MC, f"neoforge: {mc_range}", "local")

            # 4. Quilt (quilt.mod.json)
            quilt_json = read_zip_text(z, "quilt.mod.json")
            if quilt_json:
                try:
                    meta = json.loads(quilt_json)
                except json.JSONDecodeError:
                    pass
                else:
                    mod_name = meta.get("quilt_loader", {}).get("metadata", {}).get("name")
                    mod_version = meta.get("quilt_loader", {}).get("version")
                    
                    if expected_loader and expected_loader.lower() not in ("quilt", "fabric"):
                         return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_LOADER, "is_quilt", "local", mod_name, mod_version)
                    
                    # depends
                    # "quilt_loader": { "depends": [ { "id": "minecraft", "versions": ">=1.19" } ] }
                    depends = meta.get("quilt_loader", {}).get("depends", [])
                    mc_ver_limit = None
                    for dep in depends:
                        if isinstance(dep, dict) and dep.get("id") == "minecraft":
                            mc_ver_limit = dep.get("versions")
                            break
                    
                    if mc_ver_limit:
                        # Normalize string or list
                        if isinstance(mc_ver_limit, str):
                            if eval_simple_constraints(target_mc, mc_ver_limit):
                                return ModCheckResult(file_name, jar_path, CheckStatus.OK, f"quilt: {mc_ver_limit}", "local", mod_name, mod_version)
                            else:
                                return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_MC, f"quilt: {mc_ver_limit}", "local", mod_name, mod_version)
            det_loader = heuristic_detect_loader(file_name)
            det_versions = heuristic_detect_mc_versions(file_name)
            if det_loader or det_versions:
                if expected_loader:
                    compat_set = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
                    if det_loader and det_loader.lower() not in compat_set:
                        return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_LOADER, f"heuristic_loader: {det_loader}", "local")
                if det_versions:
                    if mc_version_compatible(target_mc, det_versions, relaxed_mc):
                        return ModCheckResult(file_name, jar_path, CheckStatus.OK, f"heuristic: {det_versions}", "local")
                    else:
                        return ModCheckResult(file_name, jar_path, CheckStatus.WRONG_MC, f"heuristic: {det_versions}", "local")
    except Exception:
        pass

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

def heuristic_detect_mc_versions(name: str) -> list[str]:
    s = name.lower()
    primary = [m.group(1) for m in re.finditer(r'(?:mc|minecraft|for)[-_ ]?([0-9]+\.[0-9]+(?:\.[0-9]+)?)', s)]
    if primary:
        return list(dict.fromkeys(primary))
    base = os.path.splitext(name)[0]
    tokens = re.findall(r'([0-9]+\.[0-9]+(?:\.[0-9]+)?)', base)
    if len(tokens) == 1:
        return tokens
    return []


def mc_version_compatible(target: str, supported: list[str], relaxed: bool = False) -> bool:
    if target in supported:
        return True
    if relaxed:
        # 1.20.1 -> 1.20
        major_minor = ".".join(target.split(".")[:2])
        if major_minor in supported:
            return True
    return False


def process_modrinth_result(
    file_name: str, 
    file_path: str, 
    mr_data: dict, 
    target_mc: str, 
    expected_loader: Optional[str], 
    relaxed_mc: bool
) -> ModCheckResult:
    supported = mr_data.get("game_versions") or []
    loaders = mr_data.get("loaders") or []
    
    ok_mc = mc_version_compatible(target_mc, supported, relaxed=relaxed_mc)
    
    ok_loader = True
    if expected_loader:
        compat_set = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
        mod_loaders_lower = [str(x).lower() for x in loaders]
        if loaders and not any(l in compat_set for l in mod_loaders_lower):
            ok_loader = False
        
    project_id = mr_data.get("project_id")
    version_id = mr_data.get("id")
    mr_url = f"https://modrinth.com/mod/{project_id}/version/{version_id}" if project_id and version_id else None

    if ok_mc and ok_loader:
            return ModCheckResult(file_name, file_path, CheckStatus.OK, "modrinth_ok", "modrinth", mr_data.get("name"), mr_data.get("version_number"), url=mr_url)
    else:
        if not ok_mc:
                return ModCheckResult(file_name, file_path, CheckStatus.WRONG_MC, f"modrinth_ver: {supported}", "modrinth", mr_data.get("name"), mr_data.get("version_number"), url=mr_url)
        elif not ok_loader:
                return ModCheckResult(file_name, file_path, CheckStatus.WRONG_LOADER, f"modrinth_loader: {loaders}", "modrinth", mr_data.get("name"), mr_data.get("version_number"), url=mr_url)
    return ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "logic_error", "modrinth")


def process_curseforge_result(
    file_name: str,
    file_path: str,
    f_obj: dict,
    target_mc: str,
    expected_loader: Optional[str],
    relaxed_mc: bool
) -> ModCheckResult:
    game_versions = f_obj.get("gameVersions", [])
    mod_name = f_obj.get("displayName") or f_obj.get("fileName")
    file_id = f_obj.get("id")
    
    mc_versions_in_cf = [v for v in game_versions if MC_VERSION_RE.match(v)]
    loaders_in_cf = [v.lower() for v in game_versions if v.lower() in KNOWN_LOADERS]
    
    is_mc_ok = mc_version_compatible(target_mc, mc_versions_in_cf, relaxed_mc)
    
    is_loader_ok = True
    if expected_loader:
        compat_set = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
        if loaders_in_cf and not any(l in compat_set for l in loaders_in_cf):
            is_loader_ok = False
    
    status = CheckStatus.OK
    reason = "match"
    
    if not is_mc_ok:
        status = CheckStatus.WRONG_MC
        reason = f"support: {mc_versions_in_cf}"
    elif not is_loader_ok:
        status = CheckStatus.UNKNOWN_LOADER
        reason = f"loaders: {loaders_in_cf}"
    
    cf_url = f"https://www.curseforge.com/minecraft/mc-mods/unknown/files/{file_id}" if file_id else None
    
    return ModCheckResult(
        file_name=file_name,
        file_path=file_path,
        status=status,
        reason=reason,
        source="curseforge",
        mod_name=mod_name,
        mod_version=f_obj.get("fileName"),
        url=cf_url
    )


def check_one_mod(
    jar_path: str,
    target_mc: str,
    expected_loader: Optional[str] = None,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_s: float = 10.0,
    retry: int = 2,
    sleep_s: float = 0.1,
    cache_mgr: Optional[CacheManager] = None,
    relaxed_mc: bool = False,
    cf_client: Optional[CurseForgeClient] = None,
) -> Optional[ModCheckResult]:
    """
    检查单个 jar 文件。
    1. 计算 SHA1。
    2. 查缓存。
    3. 查 Modrinth API。
    4. 如果失败/不匹配，尝试本地 metadata。
    5. (可选) 查 CurseForge API。
    6. 返回结果。
    """
    file_name = os.path.basename(jar_path)
    file_path = os.path.abspath(jar_path)

    sha1 = sha1_file(jar_path)
    if not sha1:
        return ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "read_error", "local")

    # 2. Cache
    cache_key = f"{sha1}|{target_mc}|{expected_loader or 'none'}|{relaxed_mc}"
    if cache_mgr:
        cached = cache_mgr.get(cache_key)
        if cached:
            if "status" in cached:
                return ModCheckResult(
                    file_name=file_name,
                    file_path=file_path,
                    status=CheckStatus(cached["status"]),
                    reason=cached.get("reason", ""),
                    source=cached.get("source", "cache"),
                    mod_name=cached.get("mod_name"),
                    mod_version=cached.get("mod_version"),
                    url=cached.get("url"),
                    timestamp=cached.get("timestamp")
                )

    # 3. Modrinth Check
    mr_res_data, mr_reason = query_modrinth_by_sha1(sha1, user_agent=user_agent, timeout_s=timeout_s, retry=retry)
    if sleep_s > 0:
        if mr_reason == "rate_limited" or mr_reason == "network_error" or (mr_reason.startswith("http_") and mr_reason != "http_404"):
            time.sleep(sleep_s)

    mr_res: Optional[ModCheckResult] = None
    
    if mr_res_data:
        supported = mr_res_data.get("game_versions") or []
        loaders = mr_res_data.get("loaders") or []
        
        ok_mc = mc_version_compatible(target_mc, supported, relaxed=relaxed_mc)
        
        ok_loader = True
        if expected_loader:
            compat_set = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
            mod_loaders_lower = [str(x).lower() for x in loaders]
            
            # Check intersection
            if loaders and not any(l in compat_set for l in mod_loaders_lower):
                ok_loader = False
            
        project_id = mr_res_data.get("project_id")
        version_id = mr_res_data.get("id")
        mr_url = f"https://modrinth.com/mod/{project_id}/version/{version_id}" if project_id and version_id else None

        if ok_mc and ok_loader:
             mr_res = ModCheckResult(file_name, file_path, CheckStatus.OK, f"modrinth_ok: {mr_reason}", "modrinth", mr_res_data.get("name"), mr_res_data.get("version_number"), url=mr_url)
        else:
            if not ok_mc:
                 mr_res = ModCheckResult(file_name, file_path, CheckStatus.WRONG_MC, f"modrinth_ver: {supported}", "modrinth", mr_res_data.get("name"), mr_res_data.get("version_number"), url=mr_url)
            elif not ok_loader:
                 mr_res = ModCheckResult(file_name, file_path, CheckStatus.WRONG_LOADER, f"modrinth_loader: {loaders}", "modrinth", mr_res_data.get("name"), mr_res_data.get("version_number"), url=mr_url)
    else:
        # Map Modrinth errors
        status_if_fail = CheckStatus.UNKNOWN
        if mr_reason == "not_found":
            status_if_fail = CheckStatus.NOT_FOUND
        elif mr_reason == "network_error" or mr_reason.startswith("http_"):
            status_if_fail = CheckStatus.NETWORK_ERROR
        mr_res = ModCheckResult(file_name, file_path, status_if_fail, mr_reason, "modrinth_fail")

    final_res = mr_res

    # 4. Local Metadata (Priority: Modrinth -> Local -> CF)
    if final_res.status in (CheckStatus.NOT_FOUND, CheckStatus.NETWORK_ERROR, CheckStatus.UNKNOWN):
        local_res = try_local_metadata_check(jar_path, target_mc, expected_loader, relaxed_mc)
        if local_res:
            final_res = local_res

    # 5. CurseForge Check (Fallback if Modrinth AND Local failed)
    if final_res.status in (CheckStatus.NOT_FOUND, CheckStatus.NETWORK_ERROR, CheckStatus.UNKNOWN) and cf_client:
        cf_hash = compute_curseforge_hash(jar_path)
        if cf_hash:
            match = cf_client.get_fingerprint_match(cf_hash)
            if match:
                f_obj = match.get("file", {})
                game_versions = f_obj.get("gameVersions", [])
                mod_name = f_obj.get("displayName") or f_obj.get("fileName")
                file_id = f_obj.get("id")
                
                # CF Parsing Logic
                mc_versions_in_cf = [v for v in game_versions if MC_VERSION_RE.match(v)]
                loaders_in_cf = [v.lower() for v in game_versions if v.lower() in KNOWN_LOADERS]
                
                is_mc_ok = mc_version_compatible(target_mc, mc_versions_in_cf, relaxed_mc)
                
                is_loader_ok = True
                if expected_loader:
                    compat_set = LOADER_COMPAT.get(expected_loader.lower(), {expected_loader.lower()})
                    if loaders_in_cf and not any(l in compat_set for l in loaders_in_cf):
                        is_loader_ok = False
                
                status = CheckStatus.OK
                reason = "match"
                
                if not is_mc_ok:
                    status = CheckStatus.WRONG_MC
                    reason = f"support: {mc_versions_in_cf}"
                elif not is_loader_ok:
                    status = CheckStatus.UNKNOWN_LOADER
                    reason = f"loaders: {loaders_in_cf}"
                
                cf_url = f"https://www.curseforge.com/minecraft/mc-mods/unknown/files/{file_id}" if file_id else None
                
                final_res = ModCheckResult(
                    file_name=file_name,
                    file_path=file_path,
                    status=status,
                    reason=reason,
                    source="curseforge",
                    mod_name=mod_name,
                    mod_version=f_obj.get("fileName"),
                    url=cf_url
                )

    # 6. Save to cache
    if cache_mgr and final_res.status != CheckStatus.NETWORK_ERROR:
        cache_mgr.set(cache_key, {
            "status": final_res.status.value,
            "reason": final_res.reason,
            "source": final_res.source,
            "mod_name": final_res.mod_name,
            "mod_version": final_res.mod_version,
            "url": final_res.url,
            "timestamp": time.time(),
        })

    return final_res


def print_table(results: list[ModCheckResult]) -> None:
    rows = []
    for r in results:
        extra = ""
        if r.mod_name or r.mod_version:
            extra = f"{r.mod_name or ''} {r.mod_version or ''}".strip()
        rows.append((r.status.value, r.file_name, r.source, r.reason, extra))

    col_w = [
        max(len(row[i]) for row in rows) if rows else 0
        for i in range(5)
    ]
    headers = ("STATUS", "FILE", "SOURCE", "REASON", "MODRINTH")
    col_w = [max(col_w[i], len(headers[i])) for i in range(5)]

    def fmt(row: tuple[str, str, str, str, str]) -> str:
        return "  ".join(row[i].ljust(col_w[i]) for i in range(5)).rstrip()

    print(fmt(headers))
    print(fmt(tuple("-" * w for w in col_w)))
    for row in rows:
        print(fmt(row))



class ToolTip:
    def __init__(self, widget, text=''):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.show_tip()

    def leave(self, event=None):
        self.hide_tip()

    def show_tip(self):
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

    def update_text(self, text):
        self.text = text


class ModCheckerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.geometry("900x600")

        # Load Config
        self.config = ConfigManager()

        # Variables
        self.dir_var = tk.StringVar(value=self.config.get("last_dir", os.getcwd()))
        self.mc_var = tk.StringVar(value=self.config.get("last_mc", "1.20.1"))
        self.loader_var = tk.StringVar(value=self.config.get("last_loader", ""))
        
        # Set Global Lang
        global CURRENT_LANG
        CURRENT_LANG = self.config.get("language", "en")
        if CURRENT_LANG not in LANGUAGES:
            CURRENT_LANG = "en"
            
        self.lang_var = tk.StringVar(value=CURRENT_LANG)
        self.threads_var = tk.IntVar(value=self.config.get("threads", 4))
        self.relaxed_var = tk.BooleanVar(value=self.config.get("relaxed_mc", False))
        self.no_cache_var = tk.BooleanVar(value=self.config.get("no_cache", False))
        self.cf_key_var = tk.StringVar(value=self.config.get("cf_api_key", ""))
        
        self.is_running = False
        self.stop_event = False
        
        self.results_data: list[ModCheckResult] = [] # Cache for repopulating tree on lang change

        self.setup_menu()

        # --- UI Setup ---
        
        # Top Frame: Settings
        top_frame = ttk.Frame(root, padding=10)
        top_frame.pack(fill=tk.X)

        # Row 1: Dir
        self.lbl_dir = ttk.Label(top_frame)
        self.lbl_dir.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.ent_dir = ttk.Entry(top_frame, textvariable=self.dir_var, width=50)
        self.ent_dir.grid(row=0, column=1, padx=5, pady=5)
        
        self.btn_browse = ttk.Button(top_frame, command=self.browse_dir)
        self.btn_browse.grid(row=0, column=2, padx=5, pady=5)

        # Row 2: MC Version & Loader
        self.lbl_mc = ttk.Label(top_frame)
        self.lbl_mc.grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.ent_mc = ttk.Entry(top_frame, textvariable=self.mc_var, width=15)
        self.ent_mc.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.lbl_loader = ttk.Label(top_frame)
        self.lbl_loader.grid(row=1, column=1, sticky=tk.E, padx=5, pady=5)
        
        self.cb_loader = ttk.Combobox(top_frame, textvariable=self.loader_var, values=["", "fabric", "forge", "neoforge", "quilt"], width=10, state="readonly")
        self.cb_loader.grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)

        # Row 3: Options
        opts_frame = ttk.Frame(top_frame)
        opts_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        self.chk_relaxed = ttk.Checkbutton(opts_frame, variable=self.relaxed_var)
        self.chk_relaxed.pack(side=tk.LEFT, padx=5)
        
        self.chk_no_cache = ttk.Checkbutton(opts_frame, variable=self.no_cache_var)
        self.chk_no_cache.pack(side=tk.LEFT, padx=5)
        
        self.lbl_threads = ttk.Label(opts_frame)
        self.lbl_threads.pack(side=tk.LEFT, padx=5)
        
        self.sp_threads = ttk.Spinbox(opts_frame, from_=1, to=32, textvariable=self.threads_var, width=3)
        self.sp_threads.pack(side=tk.LEFT)
        
        # Language Switcher
        self.lbl_lang = ttk.Label(opts_frame)
        self.lbl_lang.pack(side=tk.LEFT, padx=(20, 5))
        
        self.cb_lang = ttk.Combobox(opts_frame, textvariable=self.lang_var, values=list(LANGUAGES.keys()), width=8, state="readonly")
        self.cb_lang.pack(side=tk.LEFT)
        self.cb_lang.bind("<<ComboboxSelected>>", self.on_lang_change)

        # Row 4: CurseForge API Key
        self.lbl_cf_key = ttk.Label(top_frame)
        self.lbl_cf_key.grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        
        # self.cf_key_var is already initialized
        self.ent_cf_key = ttk.Entry(top_frame, textvariable=self.cf_key_var, width=35)
        self.ent_cf_key.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        self.btn_get_key = ttk.Button(top_frame, command=self.open_tutorial)
        self.btn_get_key.grid(row=3, column=2, sticky=tk.W, padx=5, pady=5)

        # Action Buttons
        self.btn_start = ttk.Button(top_frame, command=self.start_check)
        self.btn_start.grid(row=4, column=0, columnspan=3, pady=10, sticky=tk.EW)

        # Tooltips initialization
        self.tt_browse = ToolTip(self.btn_browse)
        self.tt_mc = ToolTip(self.ent_mc)
        self.tt_loader = ToolTip(self.cb_loader)
        self.tt_relaxed = ToolTip(self.chk_relaxed)
        self.tt_no_cache = ToolTip(self.chk_no_cache)
        self.tt_threads = ToolTip(self.sp_threads)
        self.tt_lang = ToolTip(self.cb_lang)
        self.tt_cf_key = ToolTip(self.ent_cf_key)
        self.tt_get_key = ToolTip(self.btn_get_key)
        self.tt_start = ToolTip(self.btn_start)

        # Results Table
        cols = ("status", "file", "source", "reason", "mod_name")
        self.tree = ttk.Treeview(root, columns=cols, show="headings")
        
        # Scrollbar
        sb = ttk.Scrollbar(root, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        # Status Bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Initial UI Text Update
        self._update_ui_text()
        self.status_var.set(tr("ready"))
        
        # Configure tags
        self.tree.tag_configure("ok", background="#e6fffa")  # light green
        self.tree.tag_configure("fail", background="#fff5f5") # light red

    def _update_ui_text(self):
        """Update all static UI texts based on CURRENT_LANG."""
        self.setup_menu()
        self.root.title(tr("window_title"))
        
        self.lbl_dir.config(text=tr("select_folder"))
        self.btn_browse.config(text=tr("browse"))
        self.lbl_mc.config(text=tr("mc_version"))
        self.lbl_loader.config(text=tr("loader"))
        
        self.chk_relaxed.config(text=tr("relaxed"))
        self.chk_no_cache.config(text=tr("no_cache"))
        self.lbl_threads.config(text=tr("threads"))
        self.lbl_lang.config(text=tr("language"))

        self.lbl_cf_key.config(text=tr("cf_api_key"))
        self.btn_get_key.config(text=tr("get_key"))
        
        # Tooltips
        self.tt_browse.update_text(tr("tooltip_browse"))
        self.tt_mc.update_text(tr("tooltip_mc_version"))
        self.tt_loader.update_text(tr("tooltip_loader"))
        self.tt_relaxed.update_text(tr("tooltip_relaxed"))
        self.tt_no_cache.update_text(tr("tooltip_no_cache"))
        self.tt_threads.update_text(tr("tooltip_threads"))
        self.tt_lang.update_text(tr("tooltip_lang"))
        self.tt_cf_key.update_text(tr("tooltip_cf_key"))
        self.tt_get_key.update_text(tr("tutorials"))
        self.tt_start.update_text(tr("tooltip_start") if not self.is_running else tr("tooltip_stop"))
        
        # Button state text
        if self.is_running:
            self.btn_start.config(text=tr("stop"))
        else:
            self.btn_start.config(text=tr("start_check"))
            
        # Treeview Headers
        cols = ("status", "file", "source", "reason", "mod_name")
        for col in cols:
            self.tree.heading(col, text=tr(col))
        
        # Repopulate tree to update translated content (Status column)
        self._refresh_tree_content()

    def _refresh_tree_content(self):
        # Clear current items
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        # Re-add all cached results
        for r in self.results_data:
            self._insert_tree_row(r)

    def on_lang_change(self, event):
        global CURRENT_LANG
        CURRENT_LANG = self.lang_var.get()
        self._update_ui_text()
        self._save_config()

    def _save_config(self):
        self.config.set("cf_api_key", self.cf_key_var.get().strip())
        self.config.set("language", self.lang_var.get())
        self.config.set("threads", self.threads_var.get())
        self.config.set("relaxed_mc", self.relaxed_var.get())
        self.config.set("no_cache", self.no_cache_var.get())
        self.config.set("last_dir", self.dir_var.get())
        self.config.set("last_mc", self.mc_var.get())
        self.config.set("last_loader", self.loader_var.get())
        self.config.save()

    def open_tutorial(self):
        tutorials = self.config.get("tutorials", [])
        if tutorials:
             url = "https://console.curseforge.com/"
             for t in tutorials:
                 if "key" in t.get("title", "").lower():
                     url = t.get("url")
                     break
             webbrowser.open(url)

    def browse_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_var.set(d)

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        self.tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=self.tr("tools"), menu=self.tools_menu)
        self.tools_menu.add_command(label=self.tr("test_api"), command=self.test_api_connections)

    def test_api_connections(self):
        def run_test():
            # CurseForge
            cf_key = self.cf_key_var.get().strip()
            cf_client = CurseForgeClient(cf_key)
            cf_ok = cf_client.check_connection()
            
            # Modrinth
            mr_client = ModrinthClient()
            mr_ok = mr_client.check_connection()
            
            tr = self.tr
            msg = f"Modrinth API: {tr('api_ok') if mr_ok else tr('api_fail')}\n"
            msg += f"CurseForge API: {tr('api_ok') if cf_ok else tr('api_fail')}"
            if not cf_key:
                 msg += " (No Key)"
            
            self.root.after(0, lambda: messagebox.showinfo(tr("api_status"), msg))

        Thread(target=run_test, daemon=True).start()

    def start_check(self):
        self._save_config()
        if self.is_running:
            self.stop_event = True
            self.btn_start.config(state=tk.DISABLED)
            return

        target_dir = self.dir_var.get()
        target_mc = self.mc_var.get()
        
        if not target_dir or not os.path.isdir(target_dir):
            messagebox.showerror(tr("error"), tr("select_dir_msg"))
            return
        if not target_mc:
            messagebox.showerror(tr("error"), tr("enter_mc_msg"))
            return

        # Clear data
        self.results_data.clear()
        self._refresh_tree_content()

        self.is_running = True
        self.stop_event = False
        self.btn_start.config(text=tr("stop"), state=tk.NORMAL)
        self.tt_start.update_text(tr("tooltip_stop"))
        
        # Run in thread
        t = Thread(target=self._run_check, args=(target_dir, target_mc), daemon=True)
        t.start()

    def _run_check(self, root_dir, target_mc):
        try:
            jars = sorted(iter_jar_files(root_dir))
            total = len(jars)
            if total == 0:
                self.root.after(0, self._finish_check, 0)
                return

            cache_mgr = None
            if not self.no_cache_var.get():
                cache_mgr = CacheManager(root_dir)

            loader = self.loader_var.get() or None
            user_agent = DEFAULT_USER_AGENT
            relaxed = self.relaxed_var.get()
            
            cf_key = self.cf_key_var.get().strip()
            cf_client = CurseForgeClient(cf_key) if cf_key else None
            mr_client = ModrinthClient(user_agent)

            # Phase 1: Hashing (Parallel)
            self.root.after(0, self._update_status, tr("scanning").format("Hashing..."))
            
            # Struct to hold file info: path, name, sha1, cf_hash
            file_infos = []

            def compute_hashes(path):
                if self.stop_event: return None
                s1 = sha1_file(path)
                cf = compute_curseforge_hash(path) if cf_client else 0
                return (path, s1, cf)

            max_workers = self.threads_var.get()
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(compute_hashes, jar): jar for jar in jars}
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    if self.stop_event: break
                    try:
                        res = future.result()
                        if res:
                            file_infos.append(res)
                    except Exception:
                        pass
                    self.root.after(0, self._update_status, tr("scanning").format(f"Hashing {i+1}/{total}"))

            if self.stop_event:
                self.root.after(0, self._finish_check, 0)
                return

            # Phase 2: Check Cache
            missing_in_cache = [] # List of (path, sha1, cf_hash)
            
            for path, s1, cf_h in file_infos:
                file_name = os.path.basename(path)
                file_path = os.path.abspath(path)
                
                if not s1:
                    # Hash failed
                    res = ModCheckResult(file_name, file_path, CheckStatus.UNKNOWN, "read_error", "local")
                    self.root.after(0, self._handle_new_result, res)
                    continue

                cache_key = f"{s1}|{target_mc}|{loader or 'none'}|{relaxed}"
                cached = cache_mgr.get(cache_key) if cache_mgr else None
                
                if cached and "status" in cached:
                    res = ModCheckResult(
                        file_name=file_name,
                        file_path=file_path,
                        status=CheckStatus(cached["status"]),
                        reason=cached.get("reason", ""),
                        source=cached.get("source", "cache"),
                        mod_name=cached.get("mod_name"),
                        mod_version=cached.get("mod_version"),
                        url=cached.get("url"),
                        timestamp=cached.get("timestamp")
                    )
                    self.root.after(0, self._handle_new_result, res)
                else:
                    missing_in_cache.append((path, s1, cf_h))

            # Phase 3: Modrinth Batch
            if missing_in_cache and not self.stop_event:
                self.root.after(0, self._update_status, tr("scanning").format("Modrinth Batch..."))
                
                # Prepare map sha1 -> info
                hashes_to_query = [item[1] for item in missing_in_cache]
                
                mr_results = mr_client.get_versions_by_hashes(hashes_to_query)
                
                still_missing = []
                
                for path, s1, cf_h in missing_in_cache:
                    if self.stop_event: break
                    file_name = os.path.basename(path)
                    file_path = os.path.abspath(path)
                    
                    if s1 in mr_results:
                        # Found in Modrinth
                        res = process_modrinth_result(file_name, file_path, mr_results[s1], target_mc, loader, relaxed)
                        self.root.after(0, self._handle_new_result, res)
                        
                        # Save to cache
                        if cache_mgr and res.status != CheckStatus.NETWORK_ERROR:
                            cache_key = f"{s1}|{target_mc}|{loader or 'none'}|{relaxed}"
                            cache_mgr.set(cache_key, {
                                "status": res.status.value,
                                "reason": res.reason,
                                "source": res.source,
                                "mod_name": res.mod_name,
                                "mod_version": res.mod_version,
                                "url": res.url,
                                "timestamp": time.time(),
                            })
                    else:
                        still_missing.append((path, s1, cf_h))

                # Phase 4: Local Fallback
                final_missing_for_cf = []
                
                for path, s1, cf_h in still_missing:
                    if self.stop_event: break
                    
                    # Try local
                    local_res = try_local_metadata_check(path, target_mc, loader, relaxed)
                    if local_res:
                         self.root.after(0, self._handle_new_result, local_res)
                         # Cache local result
                         if cache_mgr:
                            cache_key = f"{s1}|{target_mc}|{loader or 'none'}|{relaxed}"
                            cache_mgr.set(cache_key, {
                                "status": local_res.status.value,
                                "reason": local_res.reason,
                                "source": local_res.source,
                                "mod_name": local_res.mod_name,
                                "mod_version": local_res.mod_version,
                                "url": local_res.url,
                                "timestamp": time.time(),
                            })
                    else:
                        final_missing_for_cf.append((path, s1, cf_h))

                # Phase 5: CurseForge Batch
                if final_missing_for_cf and cf_client and not self.stop_event:
                     self.root.after(0, self._update_status, tr("scanning").format("CurseForge Batch..."))
                     
                     fingerprints = [item[2] for item in final_missing_for_cf if item[2]]
                     cf_results = cf_client.get_fingerprint_matches(fingerprints)
                     
                     for path, s1, cf_h in final_missing_for_cf:
                        if self.stop_event: break
                        file_name = os.path.basename(path)
                        file_path = os.path.abspath(path)
                        
                        res = None
                        if cf_h in cf_results:
                            res = process_curseforge_result(file_name, file_path, cf_results[cf_h], target_mc, loader, relaxed)
                        else:
                            # Final fail
                            res = ModCheckResult(file_name, file_path, CheckStatus.NOT_FOUND, "not_found", "unknown")

                        self.root.after(0, self._handle_new_result, res)
                        
                        if cache_mgr and res.status != CheckStatus.NETWORK_ERROR:
                            cache_key = f"{s1}|{target_mc}|{loader or 'none'}|{relaxed}"
                            cache_mgr.set(cache_key, {
                                "status": res.status.value,
                                "reason": res.reason,
                                "source": res.source,
                                "mod_name": res.mod_name,
                                "mod_version": res.mod_version,
                                "url": res.url,
                                "timestamp": time.time(),
                            })
                else:
                    # No CF client or no files left
                    for path, s1, cf_h in final_missing_for_cf:
                         file_name = os.path.basename(path)
                         file_path = os.path.abspath(path)
                         res = ModCheckResult(file_name, file_path, CheckStatus.NOT_FOUND, "not_found", "unknown")
                         self.root.after(0, self._handle_new_result, res)
                         
                         if cache_mgr:
                            cache_key = f"{s1}|{target_mc}|{loader or 'none'}|{relaxed}"
                            cache_mgr.set(cache_key, {
                                "status": res.status.value,
                                "reason": res.reason,
                                "source": res.source,
                                "mod_name": res.mod_name,
                                "mod_version": res.mod_version,
                                "url": res.url,
                                "timestamp": time.time(),
                            })

            if cache_mgr:
                cache_mgr.save()
                
            self.root.after(0, self._finish_check, total)

        except Exception as e:
            print(f"GUI Error: {e}")
            self.root.after(0, self._finish_check, 0)

    def _handle_new_result(self, r: ModCheckResult):
        self.results_data.append(r)
        self._insert_tree_row(r)

    def _insert_tree_row(self, r: ModCheckResult):
        # Translate status
        status_text = r.status.value
        status_key = r.status.value.lower()
        if status_key in TRANSLATIONS["en"]:
            status_text = tr(status_key)
        
        # Color tags
        tag = "unknown"
        if r.status == CheckStatus.OK: tag = "ok"
        elif r.status in (CheckStatus.FAIL, CheckStatus.WRONG_MC, CheckStatus.WRONG_LOADER): tag = "fail"
        
        mod_name = r.mod_name or ""
        if r.mod_version:
            mod_name += f" {r.mod_version}"

        self.tree.insert("", "end", values=(
            status_text,
            r.file_name,
            r.source,
            r.reason,
            mod_name
        ), tags=(tag,))

    def _update_status(self, msg):
        self.status_var.set(msg)

    def _finish_check(self, count):
        self.is_running = False
        self.btn_start.config(text=tr("start_check"), state=tk.NORMAL)
        self.tt_start.update_text(tr("tooltip_start"))
        if self.stop_event:
            self.status_var.set(tr("stopped"))
        else:
            self.status_var.set(tr("done").format(count))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Minecraft mod compatibility.")
    parser.add_argument("dir", nargs="?", default=".", help="Directory containing .jar files")
    parser.add_argument("--mc", required=False, help="Target Minecraft version (e.g. 1.20.1)")
    parser.add_argument("--loader", choices=["fabric", "forge", "neoforge", "quilt"], help="Expected loader")
    parser.add_argument("--threads", type=int, default=4, help="Number of concurrent checks")
    parser.add_argument("--retry", type=int, default=2, help="Max retries for network requests")
    parser.add_argument("--timeout", type=float, default=10.0, help="Network timeout in seconds")
    parser.add_argument("--sleep", type=float, default=0.1, help="Sleep between requests (seconds)")
    parser.add_argument("--no-cache", action="store_true", help="Disable local cache")
    parser.add_argument("--relaxed-mc", action="store_true", help="Relaxed MC version matching (major version only)")
    parser.add_argument("--json-out", help="Output results to JSON file")
    parser.add_argument("--gui", action="store_true", help="Launch GUI mode")
    parser.add_argument("--cf-api-key", help="CurseForge Core API Key")
    
    # If no arguments provided, and we are in a context where we might default to GUI, 
    # but argparse handles 'dir' as optional.
    # However, 'mc' is required for CLI unless we are just listing or something. 
    # But let's make it optional in parser and check later if not GUI.
    
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    # Check if GUI requested or no args
    use_gui = False
    if "--gui" in argv:
        use_gui = True
    elif len(argv) == 0:
        use_gui = True

    # Check dependencies for GUI? (Tkinter is standard)
    
    if use_gui:
        # Detect language first
        global CURRENT_LANG
        CURRENT_LANG = detect_language()
        
        root = tk.Tk()
        # Add basic translation for "ready" which was missed
        TRANSLATIONS["en"]["ready"] = "Ready"
        TRANSLATIONS["zh_CN"]["ready"] = "就绪"
        TRANSLATIONS["zh_TW"]["ready"] = "就緒"
        TRANSLATIONS["ja"]["ready"] = "準備完了"
        TRANSLATIONS["ko"]["ready"] = "준비됨"
        
        app = ModCheckerGUI(root)
        root.mainloop()
        return 0

    # CLI Mode
    args = parse_args(argv)
    
    if not args.mc:
        print("Error: --mc <version> is required for CLI mode.", file=sys.stderr)
        return 2
    
    root = os.path.abspath(args.dir)
    if not os.path.isdir(root):
        print(f"Directory not found: {root}", file=sys.stderr)
        return 2

    jars = sorted(iter_jar_files(root))
    if not jars:
        print(f"No .jar files found in: {root}", file=sys.stderr)
        return 1

    cache_mgr = None
    if not args.no_cache:
        cache_mgr = CacheManager(root)
        
    cf_client = None
    if args.cf_api_key:
        cf_client = CurseForgeClient(args.cf_api_key)

    results: list[ModCheckResult] = []
    
    # Wrapper for concurrent calls
    def process_one(path: str) -> ModCheckResult:
        return check_one_mod(
            jar_path=path,
            target_mc=args.mc,
            expected_loader=args.loader,
            user_agent=args.user_agent if hasattr(args, 'user_agent') else DEFAULT_USER_AGENT,
            timeout_s=args.timeout,
            retry=args.retry,
            sleep_s=max(args.sleep, 0.0),
            cache_mgr=cache_mgr,
            relaxed_mc=args.relaxed_mc,
            cf_client=cf_client
        )

    # 使用 ThreadPoolExecutor 并发处理
    max_workers = max(1, args.threads)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_jar = {executor.submit(process_one, jar): jar for jar in jars}
        
        # 按完成顺序处理，但为了保持列表有序，我们最后再排序或者按 jars 顺序收集
        # 这里为了简单，我们等待所有完成，然后按文件名排序输出
        completed_futures = concurrent.futures.as_completed(future_to_jar)
        
        temp_results = []
        for future in completed_futures:
            try:
                res = future.result()
                temp_results.append(res)
            except Exception as e:
                # 理论上 check_one_mod 内部捕获了大部分异常，但以防万一
                jar_p = future_to_jar[future]
                print(f"Error processing {os.path.basename(jar_p)}: {e}", file=sys.stderr)
                
    # 保持输出顺序一致
    results = sorted(temp_results, key=lambda r: r.file_name.lower())

    if cache_mgr:
        cache_mgr.save()

    print_table(results)

    if args.json_out:
        out_path = os.path.abspath(args.json_out)
        with open(out_path, "w", encoding="utf-8") as f:
            # Enum 转 str
            dump_data = []
            for r in results:
                d = r.__dict__.copy()
                d["status"] = r.status.value
                dump_data.append(d)
            json.dump(dump_data, f, ensure_ascii=False, indent=2)
        print(f"\n已写入：{out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

