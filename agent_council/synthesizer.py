import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel
from .models import SiteResult, CouncilResponse, Citation
from .openai_client import reason_structured
from .config import SYNTHESIZER_MODEL

logger = logging.getLogger(__name__)

class SynthesisOutput(BaseModel):
    synthesis: str
    synthesis_citations: List[Citation]

class SynthesizerAgent:
    def __init__(self):
        self.display_name = "Lead Synthesizer Agent"
        self.system_prompt = """You are the Lead Synthesizer Agent for an industrial site selection council.
You will receive reports from multiple expert agents across various candidate sites.
Each site has an overall weighted score, and some may have cost-per-acre data.

Your job is to write a 3-5 paragraph comparative executive summary:
1. Explain the ranking (why Site X is #1).
2. Highlight any deal-breakers or severe risks identified by the Risk or Surface agents.
3. If cost data is present, evaluate value-for-money (e.g., "Site B is 80% as good as Site A but costs 50% less per acre").
4. Maintain a professional, objective, defensible tone.

Extract citations from the underlying agent reports if you reference specific data points.
"""

    async def synthesize(self, ranked_sites: List[SiteResult], weights_used: Dict[str, float], workforce_active: bool) -> CouncilResponse:
        logger.info(f"[{self.display_name}] Synthesizing final report for {len(ranked_sites)} sites.")
        
        # Prepare content for LLM
        # We need to serialize the SiteResult objects for the LLM to read
        sites_data = []
        for sr in ranked_sites:
            site_info = {
                "rank": sr.rank,
                "weighted_score": round(sr.weighted_score, 2),
                "location": {"lat": sr.site.lat, "lng": sr.site.lng, "label": sr.site.label},
                "cost_per_acre": sr.cost_per_acre,
                "agent_reports": []
            }
            for rep in sr.agent_reports:
                site_info["agent_reports"].append({
                    "agent": rep.agent_name,
                    "score": rep.score,
                    "verdict": rep.verdict,
                    "memo": rep.memo
                })
            sites_data.append(site_info)

        user_content = {
            "weights_used": weights_used,
            "workforce_active": workforce_active,
            "ranked_sites": sites_data
        }

        try:
            synth_out = await reason_structured(
                system_prompt=self.system_prompt,
                user_content=json.dumps(user_content, indent=2),
                model=SYNTHESIZER_MODEL,
                response_format=SynthesisOutput
            )
            
            return CouncilResponse(
                ranked_sites=ranked_sites,
                synthesis=synth_out.synthesis,
                synthesis_citations=synth_out.synthesis_citations,
                weights_used=weights_used,
                workforce_active=workforce_active,
                metadata={"model_used": SYNTHESIZER_MODEL}
            )
        except Exception as e:
            logger.error(f"[{self.display_name}] Synthesis failed: {e}")
            return CouncilResponse(
                ranked_sites=ranked_sites,
                synthesis=f"Synthesis failed due to an error: {e}",
                synthesis_citations=[],
                weights_used=weights_used,
                workforce_active=workforce_active,
                metadata={"error": str(e)}
            )
