"""
backend/evaluate/mireye_fetcher.py — Mireye API wrapper with SQLite cache
==========================================================================

Responsibilities:
  - Instantiate the MireyeClient using the API key from the mireye .env file
  - Resolve an address via Mireye's own geocoder (captures coordinate_match_quality)
  - Fetch Mireye fields with an additive SQLite cache (never re-fetches cached fields)
  - Run /v1/proximity drive-time queries for Energy and Transport agents

Cache design (mireye_cache table):
  - Key:  normalized_address (string from Mireye's own geocode response)
  - Value: additive JSON blob { field_name: {value, unit, source, ...}, ... }
  - Update rule: merge new fields into existing blob; bump last_updated.
    Never overwrite fields that are already present.

Logging:
  - Every cache HIT and cache MISS is logged to stdout with [CACHE] prefix
    so testing can confirm the second run avoids duplicate Mireye calls.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Locate and import the mireye_client package from its sibling directory
# ---------------------------------------------------------------------------

MIREYE_DIR = Path(__file__).parent.parent.parent.parent / "mireye"

if not MIREYE_DIR.exists():
    raise RuntimeError(
        f"Mireye directory not found at {MIREYE_DIR}. "
        "Expected layout: Desktop/mireye/ next to Desktop/chrome extension/"
    )


# ---------------------------------------------------------------------------
# .env loader — defined and called BEFORE mireye_client is imported,
# so MIREYE_API_KEY is in os.environ when MireyeConfig is first instantiated.
# ---------------------------------------------------------------------------


def _load_env_from_file(env_path: Path) -> None:
    """Load key=value pairs from a .env file into os.environ (non-overwriting)."""
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if k and not os.environ.get(k):
                    os.environ[k] = v


# Load env files in priority order (backend/.env wins, mireye/.env is fallback)
# MUST happen before mireye_client is imported so MireyeConfig picks up the key.
BACKEND_ENV = Path(__file__).parent.parent / ".env"
_load_env_from_file(BACKEND_ENV)       # backend/.env — highest priority
_load_env_from_file(MIREYE_DIR / ".env")  # mireye/.env — fallback if not in backend

# Add mireye root to sys.path so we can import mireye_client
if str(MIREYE_DIR) not in sys.path:
    sys.path.insert(0, str(MIREYE_DIR))

from mireye_client import MireyeClient, MireyeConfig  # noqa: E402
from mireye_client.exceptions import MireyeAPIError    # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def _get_mireye_client() -> MireyeClient:
    """
    Build a MireyeClient using MIREYE_API_KEY.
    The key is loaded from backend/.env (highest priority) or mireye/.env (fallback)
    at module import time above.
    """
    config = MireyeConfig()
    if not config.has_api_key:
        raise RuntimeError(
            "MIREYE_API_KEY not found. "
            f"Add it to {BACKEND_ENV} or {MIREYE_DIR / '.env'}."
        )
    return MireyeClient(config)


# ---------------------------------------------------------------------------
# Address resolution
# ---------------------------------------------------------------------------


def resolve_address(address: str) -> dict[str, Any]:
    """
    Resolve an address through Mireye's own geocoder by making a minimal
    /v1/fetch call. The geocode block in every Mireye response tells us:
      - lat, lng
      - accuracy_type: "rooftop" | "street_interpolation" | etc.
      - normalized_address: canonical form used as cache_key

    Returns:
      {
        "lat": float,
        "lng": float,
        "normalized_address": str,   ← use as cache_key
        "coordinate_match_quality": str,
        "geocode_raw": dict          ← full geocode block for storage
      }
    """
    client = _get_mireye_client()

    # Build candidates: original, deduplicated, and street-level fallback
    candidates = [address]
    clean_addr = re.sub(r"\bUSA\b,?", "", address, flags=re.IGNORECASE)
    parts = [p.strip() for p in clean_addr.split(",") if p.strip()]
    dedup_parts = list(dict.fromkeys(parts))
    if len(dedup_parts) < len(parts):
        candidates.append(", ".join(dedup_parts))

    # Street-level fallback if house number fails
    street_fallback = re.sub(r"^\d+\s+", "", dedup_parts[0]) if dedup_parts else ""
    if street_fallback and street_fallback != dedup_parts[0]:
        candidates.append(", ".join([street_fallback] + dedup_parts[1:]))

    raw_result = None
    last_err = None
    for candidate in candidates:
        try:
            raw_result = _raw_fetch(client, candidate, ["elevation"])
            break
        except Exception as e:
            last_err = e
            continue

    if not raw_result:
        raise RuntimeError(f"Mireye geocode failed for address {address!r}: {last_err}")

    geocode = raw_result.get("geocode", {})
    resolved = raw_result.get("resolved_location", {})

    lat = resolved.get("lat") or raw_result.get("lat")
    lng = resolved.get("lng") or raw_result.get("lng")

    if lat is None or lng is None:
        raise RuntimeError(
            f"Could not extract lat/lng from Mireye response for: {address!r}"
        )

    normalized_address = geocode.get("normalized_address") or address
    accuracy_type = geocode.get("accuracy_type") or "unknown"

    logger.info(
        "[GEOCODE] %r → %.6f, %.6f | quality=%s | normalized=%r",
        address, lat, lng, accuracy_type, normalized_address,
    )

    return {
        "lat": lat,
        "lng": lng,
        "normalized_address": normalized_address,
        "coordinate_match_quality": accuracy_type,
        "geocode_raw": geocode,
    }


def _raw_fetch(client: MireyeClient, address: str, fields: list[str]) -> dict[str, Any]:
    """
    Lower-level fetch that returns the raw Mireye response dict (not the
    processed stats wrapper that fetch_data() returns). Used internally to
    get the geocode block.
    """
    import urllib.request

    config = client.config
    payload = {"fields": fields, "address": address}
    url = f"{config.base_url}/v1/fetch"
    headers = config.get_headers()

    import json as _json
    data = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    import time
    with urllib.request.urlopen(req, timeout=config.timeout) as resp:
        body = resp.read().decode("utf-8")
    return _json.loads(body)


# ---------------------------------------------------------------------------
# Additive cache helpers
# ---------------------------------------------------------------------------


def _read_cache(conn, cache_key: str) -> dict[str, Any]:
    """Return the cached fields blob for cache_key, or {} if not cached."""
    row = conn.execute(
        "SELECT fields FROM mireye_cache WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if row is None:
        return {}
    try:
        return json.loads(row["fields"])
    except (json.JSONDecodeError, TypeError):
        return {}


def _write_cache(conn, cache_key: str, new_fields: dict[str, Any]) -> None:
    """
    Additive merge: load existing blob, merge new_fields (don't overwrite
    existing keys), and upsert back. Bumps last_updated to now.
    """
    existing = _read_cache(conn, cache_key)
    merged = {**new_fields, **existing}  # existing wins (don't overwrite cached values)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO mireye_cache (cache_key, fields, last_updated)
        VALUES (?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            fields = excluded.fields,
            last_updated = excluded.last_updated
        """,
        (cache_key, json.dumps(merged), now),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Main fetcher: cache-first, Mireye on miss
# ---------------------------------------------------------------------------


def fetch_fields_with_cache(
    arg1: Any,
    arg2: Any,
    arg3: Any = None,
) -> dict[str, Any]:
    """
    Fetch a set of Mireye fields for a given cache_key (normalized address).
    Supports both signature patterns:
      - fetch_fields_with_cache(cache_key, fields)
      - fetch_fields_with_cache(conn, cache_key, fields)
    """
    from main import get_db

    if isinstance(arg1, str):
        cache_key, fields, conn = arg1, arg2, arg3
    else:
        conn, cache_key, fields = arg1, arg2, arg3

    if conn is not None:
        cached = _read_cache(conn, cache_key)
    else:
        with get_db() as active_conn:
            cached = _read_cache(active_conn, cache_key)

    hits = [f for f in fields if f in cached]
    misses = [f for f in fields if f not in cached]

    if hits:
        logger.info("[CACHE HIT]  %d/%d fields for %r: %s", len(hits), len(fields), cache_key, hits)
    if misses:
        logger.info("[CACHE MISS] %d/%d fields for %r: %s", len(misses), len(fields), cache_key, misses)

    newly_fetched: dict[str, Any] = {}

    if misses:
        client = _get_mireye_client()
        # Resolve address to lat/lng location dict for Mireye fetch API
        loc_target: Any = cache_key
        try:
            geo = resolve_address(cache_key)
            loc_target = {"lat": geo["lat"], "lng": geo["lng"]}
        except Exception as err:
            logger.warning("[GEOCODE WARN] %s — falling back to raw address string", err)

        for f in misses:
            try:
                res = client.fetch_data(fields=[f], locations=[loc_target])
                results = res.get("results", [])
                if results:
                    finfo = results[0].get("fields_data", {}).get(f)
                    newly_fetched[f] = finfo
                else:
                    newly_fetched[f] = None
            except Exception:
                newly_fetched[f] = None

        if newly_fetched:
            if conn is not None:
                _write_cache(conn, cache_key, newly_fetched)
            else:
                with get_db() as active_conn:
                    _write_cache(active_conn, cache_key, newly_fetched)

    # Combine: start from cached, layer in any newly fetched
    combined = {**cached, **newly_fetched}
    return combined


# ---------------------------------------------------------------------------
# Proximity / drive-time fetcher (Energy + Transport agents)
# ---------------------------------------------------------------------------


def fetch_proximity_drive_time(
    lat: float,
    lng: float,
    curated_set: str,
    top_n: int = 3,
) -> dict[str, Any]:
    """
    Call /v1/proximity to get the nearest N locations from a curated set
    (e.g. "@power_plants", "@airports") by drive time.

    Returns a dict with "matrix" and "nearest" keys, or {} on error.
    The result is NOT cached (proximity is cheap and coordinates may change).
    """
    client = _get_mireye_client()
    try:
        origin = {"lat": lat, "lng": lng}
        result = client.proximity(
            origins=[origin],
            destinations=[curated_set],
            mode="drive_time",
        )
        logger.info(
            "[PROXIMITY] %s @ %.4f,%.4f → status=%s",
            curated_set, lat, lng, result.get("status_code"),
        )
        return result
    except MireyeAPIError as e:
        logger.warning("[PROXIMITY ERROR] %s for %s: %s", curated_set, e, curated_set)
        return {}


# ---------------------------------------------------------------------------
# Identity field fetcher (once per evaluation, not per-agent)
# ---------------------------------------------------------------------------


def fetch_identity_fields(
    arg1: Any,
    arg2: Any,
    arg3: Any = None,
) -> dict[str, Any]:
    """
    Fetch identity/jurisdiction fields (state, county, city, parcel_id, etc.)
    using the same cache mechanism as regular agent fields.
    """
    return fetch_fields_with_cache(arg1, arg2, arg3)
