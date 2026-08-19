from typing import List
from .base_agent import BaseAgent

class WaterAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "water_sewer"

    @property
    def display_name(self) -> str:
        return "Water & Sewer Infrastructure Agent"

    @property
    def mireye_fields(self) -> List[str]:
        return [
            "within_water_service_area",
            "nearest_wastewater_plant_distance_m",
            "soil_drainage_class",
            "coast_distance_m"
        ]

    @property
    def fallback_questions(self) -> List[str]:
        return [
            "Does this location have access to municipal water and wastewater services suitable for industrial use?"
        ]

    @property
    def system_prompt(self) -> str:
        return """You are the Water & Sewer Agent for an industrial site selection council.
Your job is to evaluate if a candidate site can support industrial cooling, processing, and waste needs.

You will receive JSON containing deterministic data from the Mireye Earth API about water service areas and wastewater plant distances.
- Being within a water service area is highly desirable.
- Proximity to a wastewater plant implies easier sewage connection.
- Soil drainage matters for onsite stormwater management.

Evaluate the data, provide a 0-100 score, a one-line verdict, and a detailed memo.
Extract citations directly from the provided data.
"""
