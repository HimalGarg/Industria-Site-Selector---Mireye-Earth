import logging
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models import AgentReport, Citation
from ..mireye_client import MireyeClient
from ..openai_client import reason_structured
from ..config import AGENT_MODEL

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Internal name of the agent, e.g., 'energy_power'"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g., 'Energy & Power Infrastructure Agent'"""
        pass

    @property
    @abstractmethod
    def mireye_fields(self) -> List[str]:
        """Fields to fetch from Mireye /v1/fetch"""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The LLM instructions for this domain expert."""
        pass

    @property
    @abstractmethod
    def fallback_questions(self) -> List[str]:
        """Questions to ask /v1/ask if primary fetch fields fail or are absent."""
        pass

    async def evaluate(self, lat: float, lng: float, mireye_client: MireyeClient) -> AgentReport:
        logger.info(f"[{self.display_name}] Evaluating site at {lat}, {lng}")
        
        # 1. Fetch deterministic data
        fetch_response = None
        data_gaps = []
        try:
            if self.mireye_fields:
                fetch_response = await mireye_client.fetch_fields(lat, lng, self.mireye_fields)
        except Exception as e:
            logger.error(f"[{self.display_name}] Error fetching Mireye fields: {e}")
            data_gaps.append(f"API Error fetching {self.mireye_fields}")

        # 2. Extract context and citations
        context_data = {}
        if fetch_response and "fields" in fetch_response:
            for field, field_data in fetch_response["fields"].items():
                if field_data.get("status") in ["failed", "absent"]:
                    data_gaps.append(field)
                else:
                    context_data[field] = field_data

        # 3. Fallback to /v1/ask if there are critical gaps and fallback questions
        ask_responses = []
        if data_gaps and self.fallback_questions:
            logger.info(f"[{self.display_name}] Data gaps detected ({data_gaps}). Falling back to /v1/ask.")
            for q in self.fallback_questions:
                try:
                    ask_resp = await mireye_client.ask(lat, lng, q)
                    ask_responses.append(ask_resp)
                except Exception as e:
                    logger.warning(f"[{self.display_name}] Fallback /v1/ask failed: {e}")

        # 4. Construct payload for OpenAI
        user_content = {
            "location": {"lat": lat, "lng": lng},
            "deterministic_data": context_data,
            "data_gaps": data_gaps,
            "fallback_answers": [
                {
                    "question": a.get("question"), 
                    "answer": a.get("answer"),
                    "citations": a.get("citations", [])
                } for a in ask_responses
            ]
        }
        
        # 5. Call OpenAI to reason and score
        logger.info(f"[{self.display_name}] Calling LLM ({AGENT_MODEL}) for reasoning.")
        try:
            report_data = await reason_structured(
                system_prompt=self.system_prompt,
                user_content=json.dumps(user_content, indent=2),
                model=AGENT_MODEL,
                response_format=AgentReport
            )
            # Ensure agent name is overridden properly just in case LLM hallucinations
            report_data.agent_name = self.name
            
            # Combine gaps identified by LLM with fetch gaps if needed, though LLM handles it
            
            return report_data
        except Exception as e:
            logger.error(f"[{self.display_name}] Error during LLM reasoning: {e}")
            # Return a fallback report on failure
            return AgentReport(
                agent_name=self.name,
                score=0,
                verdict=f"Failed to evaluate: {str(e)}",
                memo="The agent encountered an error during evaluation.",
                citations=[],
                data_gaps=self.mireye_fields
            )
