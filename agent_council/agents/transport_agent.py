import json
import logging
from typing import List
from .base_agent import BaseAgent
from ..models import AgentReport
from ..mireye_client import MireyeClient
from ..openai_client import reason_structured
from ..config import AGENT_MODEL

logger = logging.getLogger(__name__)

class TransportAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "transportation"

    @property
    def display_name(self) -> str:
        return "Transportation Infrastructure Agent"

    @property
    def mireye_fields(self) -> List[str]:
        return [
            "nearest_major_road_distance_m",
            "nearest_rail_distance_m",
            "nearest_airport_distance_m"
        ]

    @property
    def fallback_questions(self) -> List[str]:
        return [
            "How accessible is this location for logistics supply chains involving highways, commercial airports, and rail lines?"
        ]

    @property
    def system_prompt(self) -> str:
        return """You are the Transportation Infrastructure Agent for an industrial site selection council.
Your job is to evaluate if a candidate site has efficient access to logistics supply chains.

You will receive JSON containing deterministic data from the Mireye Earth API about proximity to major roads, rail lines, and airports.
- You may also receive drive-time proximity data for airports or rail terminals.
- Shorter distances and shorter drive times to these transportation hubs are highly positive.

Evaluate the data, provide a 0-100 score, a one-line verdict, and a detailed memo.
Extract citations directly from the provided data.
"""

    async def evaluate(self, lat: float, lng: float, mireye_client: MireyeClient) -> AgentReport:
        logger.info(f"[{self.display_name}] Evaluating site at {lat}, {lng}")
        
        # We can call the base evaluation steps, but since it returns the final report, 
        # we'll just rewrite the evaluation flow to include proximity calls.
        
        data_gaps = []
        context_data = {}
        
        try:
            fetch_response = await mireye_client.fetch_fields(lat, lng, self.mireye_fields)
            if "fields" in fetch_response:
                for field, field_data in fetch_response["fields"].items():
                    if field_data.get("status") in ["failed", "absent"]:
                        data_gaps.append(field)
                    else:
                        context_data[field] = field_data
        except Exception as e:
            logger.error(f"[{self.display_name}] Error fetching Mireye fields: {e}")
            data_gaps.append(f"API Error fetching {self.mireye_fields}")

        # Additional Proximity calls
        proximity_data = {}
        try:
            # Get nearest airport drive time
            airport_resp = await mireye_client.proximity("nearest", {"lat": lat, "lng": lng}, candidates="@airports", max_results=1)
            if "results" in airport_resp and len(airport_resp["results"]) > 0:
                proximity_data["nearest_airport_drive"] = airport_resp["results"][0]
        except Exception as e:
            logger.warning(f"[{self.display_name}] Proximity @airports failed: {e}")

        try:
            # Get nearest rail terminal drive time
            rail_resp = await mireye_client.proximity("nearest", {"lat": lat, "lng": lng}, candidates="@rail_terminals", max_results=1)
            if "results" in rail_resp and len(rail_resp["results"]) > 0:
                proximity_data["nearest_rail_terminal_drive"] = rail_resp["results"][0]
        except Exception as e:
            logger.warning(f"[{self.display_name}] Proximity @rail_terminals failed: {e}")

        ask_responses = []
        if data_gaps and self.fallback_questions:
            for q in self.fallback_questions:
                try:
                    ask_resp = await mireye_client.ask(lat, lng, q)
                    ask_responses.append(ask_resp)
                except Exception as e:
                    pass

        user_content = {
            "location": {"lat": lat, "lng": lng},
            "deterministic_data": context_data,
            "proximity_data": proximity_data,
            "data_gaps": data_gaps,
            "fallback_answers": [
                {
                    "question": a.get("question"), 
                    "answer": a.get("answer"),
                    "citations": a.get("citations", [])
                } for a in ask_responses
            ]
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
                data_gaps=self.mireye_fields
            )
