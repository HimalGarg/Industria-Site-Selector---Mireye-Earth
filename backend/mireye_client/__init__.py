import os
import json
import urllib.request
from typing import Any

from .exceptions import MireyeAPIError

class MireyeConfig:
    def __init__(self, api_key: str = None, base_url: str = None, timeout: float = 30.0):
        self.api_key = api_key or os.environ.get("MIREYE_API_KEY", "")
        self.base_url = base_url or os.environ.get("MIREYE_BASE_URL", "https://api.mireye.com")
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
        # The API expects a single lat/lng at the top level
        payload = {"fields": fields}
        if locations and isinstance(locations, list) and len(locations) > 0:
            if isinstance(locations[0], dict):
                payload["lat"] = locations[0].get("lat")
                payload["lng"] = locations[0].get("lng")
                
        raw_res = self._post(url, payload)
        # Re-map the clean API response to the format mireye_fetcher expects
        return {
            "results": [
                {
                    "fields_data": raw_res.get("fields", {})
                }
            ]
        }
        
    def proximity(self, origins: list, destinations: list, mode: str) -> dict:
        url = f"{self.config.base_url}/v1/proximity"
        
        if mode == "drive_time":
            mode = "driving"
            
        payload = {
            "op": "nearest",
            "mode": mode
        }
        
        if origins and isinstance(origins, list) and len(origins) > 0:
            origin_dict = origins[0]
            if isinstance(origin_dict, dict) and "lat" in origin_dict and "lng" in origin_dict:
                payload["origin"] = f"{origin_dict['lat']},{origin_dict['lng']}"
            elif isinstance(origin_dict, str):
                payload["origin"] = origin_dict
            
        if destinations and isinstance(destinations, list) and len(destinations) > 0:
            payload["set"] = destinations[0]
            
        # evaluate/mireye_fetcher.py expects {"nearest": ...} from the raw response because it accesses `result.get("nearest", [])` ? Wait, let me check mireye_fetcher.py
        # Actually it returns `return result` directly. Let's return raw_res.
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
