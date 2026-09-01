import os
import json
import urllib.request
from typing import Any

from .exceptions import MireyeAPIError

class MireyeConfig:
    def __init__(self, api_key: str = None, base_url: str = None, timeout: float = 30.0):
        self.api_key = api_key or os.environ.get("MIREYE_API_KEY", "")
        self.base_url = base_url or os.environ.get("MIREYE_BASE_URL", "https://api.mireye.earth")
        self.timeout = timeout
        
    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key != "your_mireye_jwt_here")
        
    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

class MireyeClient:
    def __init__(self, config: MireyeConfig):
        self.config = config
        
    def fetch_data(self, fields: list, locations: list) -> dict:
        url = f"{self.config.base_url}/v1/fetch"
        payload = {"fields": fields, "locations": locations}
        return self._post(url, payload)
        
    def proximity(self, origins: list, destinations: list, mode: str) -> dict:
        url = f"{self.config.base_url}/v1/proximity"
        payload = {"origins": origins, "destinations": destinations, "mode": mode}
        return self._post(url, payload)
        
    def _post(self, url: str, payload: dict) -> dict:
        import urllib.error
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self.config.get_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
                err_json = json.loads(error_body)
                msg = err_json.get("detail", {}).get("message", error_body)
                raise MireyeAPIError(f"API request failed: HTTP {e.code} - {msg}") from None
            except Exception:
                raise MireyeAPIError(f"API request failed: {e}") from None
        except Exception as e:
            raise MireyeAPIError(f"API request failed: {e}")
