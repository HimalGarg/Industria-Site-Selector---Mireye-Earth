from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class SiteInput(BaseModel):
    lat: float
    lng: float
    label: str = Field(default="Candidate Site")
    cost_usd: Optional[float] = None
    area_acres: Optional[float] = None

class CouncilRequest(BaseModel):
    sites: List[SiteInput]
    worker_profile: Optional[str] = None
    weights: Optional[Dict[str, float]] = None

class Citation(BaseModel):
    source: str
    source_url: str
    field: str
    confidence: str

class AgentReport(BaseModel):
    agent_name: str
    score: int = Field(ge=0, le=100)
    verdict: str
    memo: str
    citations: List[Citation]
    data_gaps: List[str]

class SiteResult(BaseModel):
    site: SiteInput
    agent_reports: List[AgentReport]
    weighted_score: float
    rank: int
    cost_per_acre: Optional[float] = None

class CouncilResponse(BaseModel):
    ranked_sites: List[SiteResult]
    synthesis: str
    synthesis_citations: List[Citation]
    weights_used: Dict[str, float]
    workforce_active: bool
    metadata: dict
