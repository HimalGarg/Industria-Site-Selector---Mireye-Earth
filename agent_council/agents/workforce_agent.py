import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .base_agent import BaseAgent
from ..models import AgentReport
from ..mireye_client import MireyeClient
from ..openai_client import reason_structured
from ..config import AGENT_MODEL

logger = logging.getLogger(__name__)

class ExtractionRequirements(BaseModel):
    max_commute_time_minutes: int = Field(default=30)
    urban_center_needed: bool = Field(default=False)

class WorkforceAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "workforce_livability"

    @property
    def display_name(self) -> str:
        return "Workforce & Livability Agent"

    @property
    def mireye_fields(self) -> List[str]:
        return []

    @property
    def fallback_questions(self) -> List[str]:
        return []

    @property
    def system_prompt(self) -> str:
        return """You are the Workforce & Livability Agent for an industrial site selection council.
Your job is to evaluate if a candidate site can attract and retain the workforce described by the user.

You will receive JSON containing:
1. The user's unstructured 'Day-in-the-Life' worker profile description.
2. Extracted commute requirements.
3. Proximity data from the Mireye Earth API (e.g. labor shed population within the commute radius).

Evaluate the data:
- High working-age population in the labor shed is positive.
- If the worker needs urban amenities, proximity to cities is important.

Provide a 0-100 score, a one-line verdict, and a detailed memo explaining how well the site fits the worker profile.
Extract citations directly from the provided data.
"""

    async def extract_requirements(self, worker_profile: str) -> ExtractionRequirements:
        """Extract commute/urban needs from unstructured worker profile."""
        system_prompt = "Extract the maximum acceptable commute time (in minutes) and whether proximity to an urban center is needed from this worker profile description."
        try:
            reqs = await reason_structured(
                system_prompt=system_prompt,
                user_content=worker_profile,
                model=AGENT_MODEL,
                response_format=ExtractionRequirements
            )
            return reqs
        except Exception as e:
            logger.warning(f"[{self.display_name}] Failed to extract requirements: {e}. Using defaults.")
            return ExtractionRequirements(max_commute_time_minutes=30, urban_center_needed=False)

    async def evaluate_workforce(self, lat: float, lng: float, worker_profile: str, mireye_client: MireyeClient) -> AgentReport:
        logger.info(f"[{self.display_name}] Evaluating site at {lat}, {lng} for workforce.")
        
        # 1. Extract requirements
        reqs = await self.extract_requirements(worker_profile)
        
        proximity_data = {}
        data_gaps = []
        
        # 2. Call labor shed
        try:
            labor_resp = await mireye_client.proximity(
                op="labor_shed",
                origin={"lat": lat, "lng": lng},
                threshold_minutes=reqs.max_commute_time_minutes
            )
            proximity_data["labor_shed"] = labor_resp
        except Exception as e:
            logger.error(f"[{self.display_name}] Error fetching labor shed: {e}")
            data_gaps.append("labor_shed")

        # 3. Get nearest urban area if needed
        if reqs.urban_center_needed:
            try:
                urban_resp = await mireye_client.proximity(
                    op="nearest",
                    origin={"lat": lat, "lng": lng},
                    candidates="@cities",
                    max_results=1
                )
                proximity_data["nearest_city"] = urban_resp
            except Exception as e:
                logger.error(f"[{self.display_name}] Error fetching nearest city: {e}")
                data_gaps.append("nearest_city")

        # 4. Reason with LLM
        user_content = {
            "worker_profile_description": worker_profile,
            "extracted_requirements": reqs.model_dump(),
            "location": {"lat": lat, "lng": lng},
            "proximity_data": proximity_data,
            "data_gaps": data_gaps
        }
        
        try:
            report_data = await reason_structured(
                system_prompt=self.system_prompt,
                user_content=json.dumps(user_content, indent=2),
                model=AGENT_MODEL,
                response_format=AgentReport
            )
            report_data.agent_name = self.name
            return report_data
        except Exception as e:
            logger.error(f"[{self.display_name}] Error during LLM reasoning: {e}")
            return AgentReport(
                agent_name=self.name,
                score=0,
                verdict=f"Failed to evaluate: {str(e)}",
                memo="The agent encountered an error during evaluation.",
                citations=[],
                data_gaps=["workforce_data"]
            )
        
    async def evaluate(self, lat: float, lng: float, mireye_client: MireyeClient) -> AgentReport:
        # Override to prevent accidental call without worker_profile
        raise NotImplementedError("Use evaluate_workforce instead.")
