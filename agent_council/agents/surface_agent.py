from typing import List
from .base_agent import BaseAgent

class SurfaceAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "surface_environment"

    @property
    def display_name(self) -> str:
        return "Surface & Environment Agent"

    @property
    def mireye_fields(self) -> List[str]:
        return [
            "elevation",
            "slope_degrees",
            "bedrock_depth_cm",
            "tree_canopy_pct",
            "ndvi_current",
            "lcms_class",
            "is_cultivated",
            "intersects_conservation_easement",
            "intersects_critical_habitat",
            "intersects_wetland"
        ]

    @property
    def fallback_questions(self) -> List[str]:
        return [
            "Is the terrain flat enough for industrial development, and are there any environmental or protected area encumbrances?"
        ]

    @property
    def system_prompt(self) -> str:
        return """You are the Surface & Environment Agent for an industrial site selection council.
Your job is to evaluate if a candidate site is flat enough to build on, isn't encumbered by federal wetlands/protected areas, and has low tree canopy to minimize clearing costs.

You will receive JSON containing deterministic data from the Mireye Earth API about terrain, land cover, and protected boundaries.
- Flat terrain (low slope) and deep bedrock are ideal for construction.
- High tree canopy implies high land clearing costs.
- Intersecting conservation easements, wetlands, or critical habitats are severe red flags (deal-breakers).

Evaluate the data, provide a 0-100 score, a one-line verdict, and a detailed memo.
Extract citations directly from the provided data.
"""
