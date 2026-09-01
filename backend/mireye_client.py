import httpx
import logging
from typing import Dict, Any, List, Optional
from .config import MIREYE_BASE_URL, MIREYE_TIMEOUT, MIREYE_API_TOKEN

logger = logging.getLogger(__name__)

class MireyeClient:
    def __init__(self):
        self.base_url = MIREYE_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {MIREYE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        self.timeout = httpx.Timeout(MIREYE_TIMEOUT)

    async def fetch_fields(self, lat: float, lng: float, fields: List[str]) -> Dict[str, Any]:
        """Fetch specific fields deterministically."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "lat": lat,
                "lng": lng,
                "fields": fields
            }
            response = await client.post(
                f"{self.base_url}/v1/fetch", 
                json=payload, 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
            
    async def fetch_preset(self, lat: float, lng: float, preset: str) -> Dict[str, Any]:
        """Fetch a bundled preset deterministically."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "lat": lat,
                "lng": lng,
                "preset": preset
            }
            response = await client.post(
                f"{self.base_url}/v1/fetch", 
                json=payload, 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def ask(self, lat: float, lng: float, question: str) -> Dict[str, Any]:
        """Ask a natural language question (fallback)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "lat": lat,
                "lng": lng,
                "question": question
            }
            response = await client.post(
                f"{self.base_url}/v1/ask", 
                json=payload, 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def proximity(self, op: str, origin: Dict[str, float], **kwargs) -> Dict[str, Any]:
        """Call proximity endpoints (distance, nearest, labor_shed)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "op": op,
                "origin": origin,
                **kwargs
            }
            response = await client.post(
                f"{self.base_url}/v1/proximity", 
                json=payload, 
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
