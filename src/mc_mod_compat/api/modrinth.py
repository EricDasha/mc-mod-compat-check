from typing import List, Dict, Optional, Any
from ..network import NetworkClient
from ..common import MODRINTH_API_URL, DEFAULT_USER_AGENT

class ModrinthClient:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.client = NetworkClient(user_agent=user_agent)
        self.base_url = MODRINTH_API_URL

    def get_versions_by_hashes(self, hashes: List[str], algorithm: str = "sha1") -> Dict[str, Any]:
        if not hashes:
            return {}
        
        url = f"{self.base_url}/version_files"
        results = {}
        chunk_size = 50
        
        for i in range(0, len(hashes), chunk_size):
            chunk = hashes[i:i+chunk_size]
            data = {"hashes": chunk, "algorithm": algorithm}
            
            status, body = self.client.post_json(url, data)
            if status == 200 and isinstance(body, dict):
                results.update(body)
                
        return results

    def check_connection(self) -> bool:
        # Check root API endpoint (https://api.modrinth.com/) which returns API info
        # self.base_url is .../v2 which returns 404 on root
        root_url = self.base_url.replace("/v2", "/")
        status, _ = self.client.get_json(root_url)
        return status == 200
