from typing import List, Optional, Any
from pydantic import BaseModel

class Finding(BaseModel):
    finding: str
    source: str
    source_type: str
    record_id: Optional[str] = None
    date: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[float] = None

class CategoryResult(BaseModel):
    status: str  # CLEAR, POTENTIAL_RISK, VIOLATION_FOUND, DATA_NOT_FOUND, DATA_UNAVAILABLE, REQUIRES_MANUAL_REVIEW
    score: Optional[int] = None
    findings: List[Finding] = []

class OverallResult(BaseModel):
    risk: str
    score: int
    confidence: int
    summary: Optional[str] = None

class PropertyContext(BaseModel):
    address: str
    latitude: Optional[float]
    longitude: Optional[float]

class ComplianceReport(BaseModel):
    property: PropertyContext
    overall: OverallResult
    environmental: CategoryResult
    building: CategoryResult
    fire: CategoryResult
    zoning: CategoryResult
    occupancy: CategoryResult
    data_sources: List[str] = []
    limitations: List[str] = []
