import asyncio
import httpx
from typing import Optional, Tuple
import logging
from functools import partial

logger = logging.getLogger(__name__)


def _nominatim_geocode_sync(address: str):
    """Synchronous Nominatim geocode — runs inside a thread executor."""
    import time
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="mireye_agent_compliance_v2")
    time.sleep(1.1)  # Respect OSM 1-req/sec rate limit (safe inside thread)
    return geolocator.geocode(address, timeout=10)


async def resolve_address(address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Resolve an address to (lat, lng, jurisdiction).

    Priority:
    1. US Census Geocoder (free, no key, very accurate for US addresses)
    2. Nominatim/OSM fallback (run in executor to avoid blocking event loop)
    3. Raw string heuristic (jurisdiction-only, no coordinates)
    """
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json"
    }
    lat, lng, jurisdiction, state, county = None, None, None, None, None

    # ── Step 1: US Census Geocoder ──────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                matches = data.get("result", {}).get("addressMatches", [])
                if matches:
                    match = matches[0]
                    coords = match.get("coordinates", {})
                    lng = coords.get("x")
                    lat = coords.get("y")
                    
                    geos = match.get("geographies", {})
                    counties = geos.get("Counties", [])
                    states = geos.get("States", [])
                    if counties: county = counties[0].get("NAME")
                    if states: state = states[0].get("STUSAB")

                    matched_addr = match.get("matchedAddress", "").upper()
                    jurisdiction = _detect_jurisdiction(matched_addr)
                    logger.info(f"[GEOCODE] Census match: lat={lat}, lng={lng}, juris={jurisdiction}, state={state}, county={county}")
    except Exception as e:
        logger.warning(f"[GEOCODE] Census Geocoder error for '{address}': {e}")

    # ── Step 2: Nominatim fallback (non-blocking via executor) ──────────────
    if lat is None or lng is None:
        try:
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(None, _nominatim_geocode_sync, address)
            if location:
                lat = location.latitude
                lng = location.longitude
                loc_addr = location.address.upper()
                jurisdiction = _detect_jurisdiction(loc_addr) or _detect_jurisdiction(address.upper())
                
                # Parse State and County from raw Nominatim response if available
                raw = location.raw.get("address", {}) if hasattr(location, "raw") else {}
                state = state or raw.get("state")
                county = county or raw.get("county")

                logger.info(f"[GEOCODE] Nominatim match: lat={lat}, lng={lng}, juris={jurisdiction}, state={state}, county={county}")
            else:
                logger.warning(f"[GEOCODE] Nominatim returned no result for '{address}'")
        except Exception as e:
            logger.error(f"[GEOCODE] Nominatim fallback error for '{address}': {e}")

    # ── Step 3: Heuristic from raw address string ────────────────────────────
    if not jurisdiction:
        jurisdiction = _detect_jurisdiction(address.upper())

    return lat, lng, jurisdiction, state, county


def _detect_jurisdiction(text: str) -> Optional[str]:
    """Detect municipality from address string."""
    text = text.upper()
    if "CHICAGO" in text:
        return "CHICAGO"
    if "NEW YORK" in text or ", NY " in text or " NY," in text:
        return "NEW YORK"
    if "SAN FRANCISCO" in text or ", SF " in text:
        return "SAN FRANCISCO"
    return None
