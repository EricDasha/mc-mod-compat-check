import urllib.request
import urllib.error
import json
import time
import socket
from typing import Optional, Any, Dict, Tuple

class NetworkError(Exception):
    pass

class RateLimitError(NetworkError):
    pass

class NetworkClient:
    def __init__(self, user_agent: str, default_timeout: float = 10.0, max_retries: int = 3):
        self.user_agent = user_agent
        self.default_timeout = default_timeout
        self.max_retries = max_retries

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> Tuple[int, Any]:
        return self._request("GET", url, headers=headers, timeout=timeout)

    def post_json(self, url: str, data: Any, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> Tuple[int, Any]:
        json_data = json.dumps(data).encode("utf-8")
        if headers is None:
            headers = {}
        headers["Content-Type"] = "application/json"
        return self._request("POST", url, data=json_data, headers=headers, timeout=timeout)

    def _request(self, method: str, url: str, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> Tuple[int, Any]:
        if headers is None:
            headers = {}
        
        headers["User-Agent"] = self.user_agent
        
        current_timeout = timeout if timeout is not None else self.default_timeout
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=current_timeout) as resp:
                    status_code = resp.status
                    content = resp.read()
                    
                    if status_code == 204: # No Content
                        return status_code, None
                        
                    try:
                        decoded_content = content.decode("utf-8")
                        if decoded_content.strip():
                            json_body = json.loads(decoded_content)
                        else:
                            json_body = None
                        return status_code, json_body
                    except json.JSONDecodeError:
                         # Fallback if not JSON
                        return status_code, content

            except urllib.error.HTTPError as e:
                # 404 is not a retryable error usually, but it is a valid response
                if e.code == 404:
                    return 404, None
                
                if e.code == 429: # Rate limit
                    wait_time = min(2 ** attempt, 60)
                    time.sleep(wait_time)
                    last_error = RateLimitError(f"Rate limited: {e}")
                    continue
                
                if 500 <= e.code < 600: # Server error
                    wait_time = min(2 ** attempt, 10)
                    time.sleep(wait_time)
                    last_error = NetworkError(f"Server error {e.code}: {e}")
                    continue
                
                # Other client errors
                return e.code, None

            except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
                wait_time = min(2 ** attempt, 5)
                time.sleep(wait_time)
                last_error = NetworkError(f"Connection error: {e}")
                continue
            
            except Exception as e:
                last_error = NetworkError(f"Unexpected error: {e}")
                break

        # If we exhausted retries
        if last_error:
            # We can log this or just return 0/None to indicate failure
            # Or raise exception? The original code returned (0, None).
            # Let's return (0, None) but maybe we should raise custom exceptions for better control?
            # For compatibility and simplicity in logic, let's return (0, None) but print debug?
            print(f"Network request failed after {self.max_retries} retries: {last_error}")
            return 0, None
        
        return 0, None

    def check_connection(self, url: str) -> bool:
        """
        Simple connectivity check
        """
        try:
            self._request("GET", url, timeout=5.0, headers={"Accept": "*/*"})
            return True
        except Exception:
            return False
