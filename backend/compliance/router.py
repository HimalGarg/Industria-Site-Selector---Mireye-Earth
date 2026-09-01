from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from .orchestrator import generate_compliance_report
from .models import ComplianceReport

router = APIRouter(prefix="/compliance", tags=["Compliance"])

DB_PATH = Path(__file__).parent.parent / "site_ranker.db"

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/{cart_item_id}", response_model=ComplianceReport)
async def get_compliance_report(cart_item_id: str):
    """
    Generate or retrieve a compliance report for a given property.
    """
    with get_db() as conn:
        # Check cache first
        cached = conn.execute(
            "SELECT report_json FROM compliance_reports WHERE cart_item_id = ?", 
            (cart_item_id,)
        ).fetchone()
        
        if cached:
            try:
                data = json.loads(cached["report_json"])
                return ComplianceReport(**data)
            except Exception as e:
                pass # Fallback to generating
                
        # Fetch property address
        item = conn.execute(
            "SELECT address FROM cart_items WHERE cart_item_id = ?",
            (cart_item_id,)
        ).fetchone()
        
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found")
            
        address = item["address"]
        
    # Generate the report
    report = await generate_compliance_report(address)
    
    # Save to cache
    report_json = json.dumps(report.model_dump())
    created_at = datetime.now(timezone.utc).isoformat()
    
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO compliance_reports (cart_item_id, report_json, created_at)
            VALUES (?, ?, ?)
            """,
            (cart_item_id, report_json, created_at)
        )
        conn.commit()
        
    return report
