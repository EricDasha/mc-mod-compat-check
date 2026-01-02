from typing import List, Dict, Optional, Any
from ..network import NetworkClient
from ..common import CURSEFORGE_API_URL, DEFAULT_USER_AGENT

class CurseForgeClient:
    def __init__(self, api_key: str, user_agent: str = DEFAULT_USER_AGENT):
        self.client = NetworkClient(user_agent=user_agent)
        self.api_key = api_key
        self.base_url = CURSEFORGE_API_URL

    def get_fingerprint_matches(self, fingerprints: List[int]) -> Dict[int, Any]:
        if not self.api_key or not fingerprints:
            return {}
            
        url = f"{self.base_url}/fingerprints"
        results = {}
        chunk_size = 50
        
        headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json"
        }
        
        for i in range(0, len(fingerprints), chunk_size):
            chunk = fingerprints[i:i+chunk_size]
            data = {"fingerprints": chunk}
            
            status, body = self.client.post_json(url, data, headers=headers)
            
            if status == 200 and isinstance(body, dict):
                matches = body.get("data", {}).get("exactMatches", [])
                for m in matches:
                    fid = m.get("id")
                    if fid:
                        results[fid] = m
                        
        return results

    def check_connection(self) -> bool:
        if not self.api_key:
            return False
        url = f"{self.base_url}/games"
        headers = {"x-api-key": self.api_key}
        status, _ = self.client.get_json(url, headers=headers)
        return status == 200
