import asyncio
import logging
from typing import List, Dict, Optional
from .models import CouncilRequest, CouncilResponse, SiteInput, SiteResult, AgentReport
from .config import DEFAULT_WEIGHTS_5, DEFAULT_WEIGHTS_6
from .mireye_client import MireyeClient
from .agents import EnergyAgent, WaterAgent, SurfaceAgent, TransportAgent, RiskAgent, WorkforceAgent
from .synthesizer import SynthesizerAgent

logger = logging.getLogger(__name__)

async def evaluate_site(
    site: SiteInput, 
    worker_profile: Optional[str], 
    mireye_client: MireyeClient
) -> SiteResult:
    logger.info(f"Starting evaluation for site: {site.label} ({site.lat}, {site.lng})")
    
    agents = [
        EnergyAgent(),
        WaterAgent(),
        SurfaceAgent(),
        TransportAgent(),
        RiskAgent()
    ]
    
    # Run infrastructure agents in parallel
    tasks = [agent.evaluate(site.lat, site.lng, mireye_client) for agent in agents]
    
    # Add workforce agent if profile is provided
    if worker_profile:
        wf_agent = WorkforceAgent()
        tasks.append(wf_agent.evaluate_workforce(site.lat, site.lng, worker_profile, mireye_client))
        agents.append(wf_agent)
        
    reports = await asyncio.gather(*tasks, return_exceptions=True)
    
    agent_reports = []
    for i, report in enumerate(reports):
        if isinstance(report, Exception):
            logger.error(f"Agent {agents[i].display_name} raised exception: {report}")
            # Add a fallback report on exception
            agent_reports.append(AgentReport(
                agent_name=agents[i].name,
                score=0,
                verdict="Failed to evaluate due to an internal error.",
                memo=f"Exception: {report}",
                citations=[],
                data_gaps=[]
            ))
        else:
            agent_reports.append(report)
            
    # Note: weighted score and rank will be calculated by the orchestrator across all sites
    
    return SiteResult(
        site=site,
        agent_reports=agent_reports,
        weighted_score=0.0, # Placeholder
        rank=0,             # Placeholder
        cost_per_acre=site.cost_usd / site.area_acres if site.cost_usd and site.area_acres else None
    )

async def run_council(request: CouncilRequest) -> CouncilResponse:
    if not request.sites or len(request.sites) > 5:
        raise ValueError("Must provide between 1 and 5 sites.")
        
    workforce_active = bool(request.worker_profile)
    
    # Determine weights
    if request.weights:
        weights = request.weights
        # Normalize weights if they don't sum to 1.0 (optional robustness)
    else:
        weights = DEFAULT_WEIGHTS_6 if workforce_active else DEFAULT_WEIGHTS_5
        
    mireye_client = MireyeClient()
    
    # Evaluate all sites in parallel
    site_tasks = [evaluate_site(site, request.worker_profile, mireye_client) for site in request.sites]
    site_results = await asyncio.gather(*site_tasks)
    
    # Calculate weighted scores
    for sr in site_results:
        total_score = 0.0
        weight_sum = 0.0
        for report in sr.agent_reports:
            w = weights.get(report.agent_name, 0.0)
            total_score += report.score * w
            weight_sum += w
            
        # If weights don't perfectly match active agents, normalize
        if weight_sum > 0:
            sr.weighted_score = total_score / weight_sum
        else:
            sr.weighted_score = 0.0
            
    # Rank sites
    site_results.sort(key=lambda x: x.weighted_score, reverse=True)
    for i, sr in enumerate(site_results):
        sr.rank = i + 1
        
    # Synthesize
    synthesizer = SynthesizerAgent()
    final_response = await synthesizer.synthesize(site_results, weights, workforce_active)
    
    return final_response
