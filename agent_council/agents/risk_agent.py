from typing import List
from .base_agent import BaseAgent

class RiskAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "risk_compliance"

    @property
    def display_name(self) -> str:
        return "Risk & Compliance Agent"

    @property
    def mireye_fields(self) -> List[str]:
        return [
            "fema_flood_zone",
            "within_floodplain_polygon",
            "nearest_rcra_tsd_distance_m",
            "ust_facilities_within_1km_count",
            "karst_exposure_class",
            "nearest_superfund_distance_m"
        ]

    @property
    def fallback_questions(self) -> List[str]:
        return [
            "Is this site at risk of flooding, or is it near any hazardous waste sites (Superfund, RCRA) or underground storage tanks?"
        ]

    @property
    def system_prompt(self) -> str:
        return """You are the Risk & Compliance Agent for an industrial site selection council.
Your job is to evaluate if a candidate site carries liabilities such as flood risk, hazardous waste proximity, or unstable ground.

You will receive JSON containing deterministic data from the Mireye Earth API about FEMA flood zones, EPA facilities (Superfund, RCRA, UST), and geological risks (Karst).
- Being within a FEMA floodplain is a major negative due to insurance costs and flood risk.
- Close proximity to Superfund or RCRA sites implies contamination liability risk.
- High Karst exposure class means sinkhole risk.

Evaluate the data, provide a 0-100 score, a one-line verdict, and a detailed memo.
Extract citations directly from the provided data.
"""
