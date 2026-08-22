"""
backend/main.py — Site Ranker Cart API (v3.3 Evaluation Pipeline)

Endpoints:
  POST /cart-items                      — add a captured site listing to the cart
  GET  /cart-items                      — retrieve cart items for a session
  POST /evaluate-site                   — start an async site evaluation (5 agents + synthesizer)
  GET  /evaluate-site/{evaluation_id}   — poll for evaluation results
  GET  /evaluate-site                   — list evaluations (optionally by cart_item_id)

Data Architecture:
  - `details` column:        100% raw unaltered scraped key-value pairs for provenance & audit.
  - `llm_structured` column: Clean, canonical, typed LLM inference schema (schema_version: "1.0").
  - `mireye_cache` table:    Additive Mireye field cache keyed by normalized address.
  - `evaluations` table:     Council evaluation results (5 agents + synthesizer output).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Load backend .env (OPENAI_API_KEY, etc.) before anything else
# ---------------------------------------------------------------------------

_BACKEND_ENV = Path(__file__).parent / ".env"
if _BACKEND_ENV.exists():
    with open(_BACKEND_ENV, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _k, _v = _k.strip(), _v.strip().strip("\"'")
                if _k and not os.environ.get(_k):
                    os.environ[_k] = _v

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Site Ranker Cart API", version="0.3.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # TODO (deploy): restrict to real domain + extension origin
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Database & Migrations
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "site_ranker.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cart_items (
                cart_item_id   TEXT PRIMARY KEY,
                session_id     TEXT NOT NULL,
                address        TEXT NOT NULL,
                source_url     TEXT,
                listing_title  TEXT,
                image_url      TEXT,
                details        TEXT,    -- JSON blob for raw details
                llm_structured TEXT,    -- JSON blob for standardized LLM schema
                added_at       TEXT NOT NULL
            )
            """
        )

        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(cart_items)").fetchall()
        }
        if "listing_title" not in existing_cols:
            conn.execute("ALTER TABLE cart_items ADD COLUMN listing_title TEXT")
        if "image_url" not in existing_cols:
            conn.execute("ALTER TABLE cart_items ADD COLUMN image_url TEXT")
        if "details" not in existing_cols:
            conn.execute("ALTER TABLE cart_items ADD COLUMN details TEXT")
        if "llm_structured" not in existing_cols:
            conn.execute("ALTER TABLE cart_items ADD COLUMN llm_structured TEXT")

        # ── Evaluation pipeline tables (migration: added in v0.3.3) ───────
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mireye_cache (
                cache_key    TEXT PRIMARY KEY,
                fields       TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                evaluation_id    TEXT PRIMARY KEY,
                cart_item_id     TEXT NOT NULL,
                overall_score    INTEGER,
                recommendation   TEXT,
                conflicts_flagged TEXT,
                agent_results    TEXT NOT NULL,
                created_at       TEXT NOT NULL
            )
            """
        )

        conn.commit()


init_db()

# ---------------------------------------------------------------------------
# Mount the evaluation pipeline router
# ---------------------------------------------------------------------------

from evaluate.router import router as evaluate_router  # noqa: E402 (after init_db)
app.include_router(evaluate_router)

# ---------------------------------------------------------------------------
# Robust Parsing & Type Normalization Helpers
# ---------------------------------------------------------------------------


def parse_number(val: Any) -> float | int | None:
    """Safely parse clean numeric values from strings like '6.75%', '19,776 SF', '0.900'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if not isinstance(val, str):
        return None
    clean = re.sub(r"[^\d.]", "", val)
    if not clean or clean == ".":
        return None
    try:
        if "." in clean:
            return float(clean)
        return int(clean)
    except ValueError:
        return None


def parse_boolean(val: Any) -> bool | None:
    """Convert 'Yes'/'No' string representations to boolean values."""
    if isinstance(val, bool):
        return val
    if not isinstance(val, str):
        return None
    v = val.strip().lower()
    if v in ("yes", "true", "1"):
        return True
    if v in ("no", "false", "0"):
        return False
    return None


def parse_date_iso(val: Any) -> str | None:
    """Convert date formats like '04/19/2017' to ISO '2017-04-19'."""
    if not val or not isinstance(val, str):
        return None
    val_clean = val.strip()

    # Match MM/DD/YYYY
    match_us = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", val_clean)
    if match_us:
        month, day, year = match_us.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    # Match YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val_clean):
        return val_clean

    return val_clean


def extract_price_display(val: Any) -> str | None:
    """Extract asking price display string without listing freshness noise."""
    if not val or not isinstance(val, str):
        return str(val) if val is not None else None
    return val.split("|")[0].strip()


def parse_price_numeric(val: Any) -> int | float | None:
    """
    Parses flat sale price numeric value (e.g. '$2,037,286' -> 2037286).
    Returns None for lease rate strings like '$16/SF/YR' per Step 6 spec.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if not isinstance(val, str):
        return None

    price_display = extract_price_display(val)
    if not price_display:
        return None

    # Do NOT parse lease rates as flat asking_price
    if re.search(r"/SF/(?:YR|MO)", price_display, re.IGNORECASE):
        return None

    match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", price_display)
    if match:
        clean = match.group(1).replace(",", "")
        try:
            return float(clean) if "." in clean else int(clean)
        except ValueError:
            return None
    return parse_number(price_display)


def parse_freshness(val: Any) -> tuple[int | None, int | None]:
    """Parses (days_on_market, days_since_update) out of raw price string."""
    if not val or not isinstance(val, str):
        return (None, None)

    dom = None
    update_days = None

    dom_match = re.search(r"(\d+)\s+days\s+on\s+market", val, re.IGNORECASE)
    if dom_match:
        dom = int(dom_match.group(1))

    upd_match = re.search(r"Updated\s+(\d+)\s+days\s+ago", val, re.IGNORECASE)
    if upd_match:
        update_days = int(upd_match.group(1))

    return (dom, update_days)


def build_llm_structured_data(
    address: str,
    listing_title: str | None,
    source_url: str | None,
    image_url: str | None,
    details: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Pure Normalization Engine:
    Transforms raw unstandardized scraper outputs into a canonical,
    non-redundant schema (schema_version: "1.0") for LLM inference.
    Does NOT mutate the original details dictionary.
    """
    d = details or {}

    raw_price = d.get("price") or d.get("Asking Price")
    price_display = extract_price_display(raw_price)
    asking_price = parse_price_numeric(raw_price)
    dom, days_updated = parse_freshness(raw_price)

    sqft_val = d.get("Square Footage") or d.get("Building Size") or d.get("Net Rentable (SqFt)")
    building_sqft = parse_number(sqft_val)

    cap_val = d.get("Cap Rate") or d.get("Pro-Forma Cap Rate")
    cap_rate = parse_number(cap_val)

    noi_val = d.get("NOI") or d.get("Pro-Forma NOI")
    noi = parse_price_numeric(noi_val)

    occ_val = d.get("Occupancy")
    occupancy = parse_number(occ_val)

    raw_highlights = d.get("highlights")
    highlights_list = []
    if isinstance(raw_highlights, list):
        highlights_list = raw_highlights
    elif isinstance(raw_highlights, str):
        highlights_list = [h.strip() for h in raw_highlights.split("|") if h.strip()]

    # Rent bumps: boolean if Yes/No, otherwise string schedule
    rent_bumps_raw = d.get("Rent Bumps")
    rent_bumps_val: bool | str | None = parse_boolean(rent_bumps_raw)
    if rent_bumps_val is None and rent_bumps_raw:
        rent_bumps_val = str(rent_bumps_raw)

    return {
        "schema_version": "1.0",
        "identity": {
            "address": address,
            "source_url": source_url,
            "listing_title": listing_title,
            "image_url": image_url,
        },
        "property": {
            "property_type": d.get("Property Type"),
            "sub_type": d.get("Sub Type"),
            "building_sqft": building_sqft,
            "lot_acres": parse_number(d.get("Acreage")),
            "year_built": parse_number(d.get("Year Built")),
            "building_class": d.get("Class"),
            "stories": parse_number(d.get("Stories")),
            "units": parse_number(d.get("Units")),
            "buildings": parse_number(d.get("Buildings")),
        },
        "financials": {
            "asking_price_display": price_display,
            "asking_price": asking_price,
            "cap_rate_percent": cap_rate,
            "noi_annual": noi,
            "occupancy_percent": occupancy,
            "price_per_sqft": parse_number(d.get("Price per SqFt")),
        },
        "lease": {
            "tenant": d.get("Brand/Tenant"),
            "tenancy": d.get("Tenancy"),
            "lease_type": d.get("Lease Type"),
            "lease_term_years": parse_number(d.get("Lease Term")),
            "lease_commencement": parse_date_iso(d.get("Lease Commencement")),
            "lease_expiration": parse_date_iso(d.get("Lease Expiration")),
            "rent_bumps": rent_bumps_val,
            "lease_options": d.get("Lease Options"),
        },
        "investment": {
            "investment_type": d.get("Investment Type"),
            "tenant_credit": d.get("Tenant Credit"),
            "ownership": d.get("Ownership"),
            "ground_lease": parse_boolean(d.get("Ground Lease")),
            "broker_co_op": parse_boolean(d.get("Broker Co-Op")),
        },
        "listing_freshness": {
            "days_on_market": dom,
            "days_since_update": days_updated,
        },
        "narrative": {
            "description": d.get("description"),
            "highlights": highlights_list,
        },
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CartItemIn(BaseModel):
    session_id: str
    address: str
    source_url: Optional[str] = None
    listing_title: Optional[str] = None
    image_url: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class CartItemOut(BaseModel):
    cart_item_id: str
    address: str
    status: str = "added"


class CartItemFull(BaseModel):
    cart_item_id: str
    address: str
    source_url: Optional[str]
    listing_title: Optional[str]
    image_url: Optional[str]
    details: Optional[dict[str, Any]]
    llm_structured: Optional[dict[str, Any]]
    added_at: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/cart-items", response_model=CartItemOut, status_code=201)
def add_cart_item(item: CartItemIn) -> CartItemOut:
    """Add a captured address/listing to the cart for a given session."""
    if not item.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")
    if not item.address.strip():
        raise HTTPException(status_code=400, detail="address is required")

    cart_item_id = str(uuid.uuid4())
    added_at = datetime.now(timezone.utc).isoformat()

    # Build standardized canonical LLM schema (schema_version: "1.0")
    llm_structured_obj = build_llm_structured_data(
        address=item.address.strip(),
        listing_title=item.listing_title,
        source_url=item.source_url,
        image_url=item.image_url,
        details=item.details,
    )

    details_json = json.dumps(item.details) if item.details else None
    llm_structured_json = json.dumps(llm_structured_obj)

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO cart_items
                (cart_item_id, session_id, address, source_url, listing_title, image_url, details, llm_structured, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cart_item_id,
                item.session_id,
                item.address.strip(),
                item.source_url,
                item.listing_title,
                item.image_url,
                details_json,
                llm_structured_json,
                added_at,
            ),
        )
        conn.commit()

    return CartItemOut(cart_item_id=cart_item_id, address=item.address.strip())


@app.get("/cart-items", response_model=list[CartItemFull])
def get_cart_items(
    session_id: Optional[str] = Query(None, description="Optional Session ID to filter by"),
) -> list[CartItemFull]:
    """Return all cart items for a session (or all items if session_id is omitted), newest first."""
    with get_db() as conn:
        if session_id and session_id.strip():
            rows = conn.execute(
                "SELECT * FROM cart_items WHERE session_id = ? ORDER BY added_at DESC",
                (session_id.strip(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM cart_items ORDER BY added_at DESC"
            ).fetchall()

    result = []
    for row in rows:
        details = None
        if row["details"]:
            try:
                details = json.loads(row["details"])
            except json.JSONDecodeError:
                details = None

        llm_structured = None
        if "llm_structured" in row.keys() and row["llm_structured"]:
            try:
                llm_structured = json.loads(row["llm_structured"])
            except json.JSONDecodeError:
                llm_structured = None

        if not llm_structured:
            llm_structured = build_llm_structured_data(
                address=row["address"],
                listing_title=row["listing_title"],
                source_url=row["source_url"],
                image_url=row["image_url"],
                details=details,
            )

        result.append(
            CartItemFull(
                cart_item_id=row["cart_item_id"],
                address=row["address"],
                source_url=row["source_url"],
                listing_title=row["listing_title"],
                image_url=row["image_url"],
                details=details,
                llm_structured=llm_structured,
                added_at=row["added_at"],
            )
        )
    return result


# ---------------------------------------------------------------------------
# Health & Root Check
# ---------------------------------------------------------------------------


@app.get("/")
def root() -> dict:
    return {
        "service": "Site Ranker Cart API",
        "version": "0.3.3",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "get_cart_items":    "/cart-items?session_id=<your_session_id>",
            "add_cart_item":     "POST /cart-items",
            "start_evaluation":  "POST /evaluate-site",
            "get_evaluation":    "GET  /evaluate-site/{evaluation_id}",
            "list_evaluations":  "GET  /evaluate-site?cart_item_id=<optional>",
        },
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "site-ranker-cart", "version": "0.3.3"}
