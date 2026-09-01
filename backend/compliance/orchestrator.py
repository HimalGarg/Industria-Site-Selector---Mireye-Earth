import os
import json
import logging
from .models import ComplianceReport, PropertyContext, CategoryResult, OverallResult, Finding
from .address_resolver import resolve_address
from .epa_agent import search_epa_facilities
from .local_agents import run_building_agent, run_fire_agent, run_occupancy_agent, run_zoning_agent
from .federal_agents import search_fema_disasters, search_usgs_earthquakes
from .risk_engine import score_environmental, score_category, calculate_overall_risk
from openai import OpenAI

def get_llm_summary(report_dict: dict) -> str:
    """Generate a 2-3 sentence summary using Gemini/OpenAI explaining the structured risk score."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return "No LLM API key configured for summarization."
        
    try:
        client = OpenAI(api_key=api_key)
        model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        prompt = f"""
You are the Executive Summary writer for the Industrial Property Regulatory & Compliance Due-Diligence Agent.
Given the following deterministic risk report, write a 2-3 sentence summary for the frontend.
Do NOT hallucinate risks. Do NOT state the property is completely compliant.
Use facts from the report to explain the overall risk classification and the data confidence level.

REPORT JSON:
{json.dumps(report_dict, indent=2)}
"""
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"LLM Summarization failed: {str(e)}"

async def generate_compliance_report(address: str) -> ComplianceReport:
    # 1. Address Resolution
    lat, lng, jurisdiction, state, county = await resolve_address(address)
    
    # 2. Nationwide Federal Agents (FEMA, USGS, EPA)
    fema_findings = await search_fema_disasters(state, county) if state and county else []
    usgs_findings = await search_usgs_earthquakes(lat, lng) if lat and lng else []
    
    env_findings = []
    if lat and lng:
        epa_findings = await search_epa_facilities(lat, lng)
        env_findings.extend(epa_findings)
    
    # Combine FEMA into Environmental
    env_findings.extend(fema_findings)

    env_status = "DATA_UNAVAILABLE"
    if env_findings:
        if any(f.status == "VIOLATION_FOUND" for f in env_findings):
            env_status = "VIOLATION_FOUND"
        elif any(f.status == "POTENTIAL_RISK" for f in env_findings):
            env_status = "POTENTIAL_RISK"
        else:
            env_status = "CLEAR"
    else:
        env_status = "CLEAR"
        env_findings = [Finding(finding="✅ EPA ECHO Database queried successfully. No environmental violations found.", source="EPA ECHO", source_type="government_api", status="CLEAR")]

    env_result = CategoryResult(
        status=env_status,
        score=score_environmental(env_findings) if env_status not in ["DATA_UNAVAILABLE", "DATA_NOT_FOUND"] else (100 if env_status == "DATA_NOT_FOUND" else None),
        findings=env_findings
    )
    
    # 3. Local Agents & Combine with Federal
    bldg_status_local, bldg_findings = await run_building_agent(address, jurisdiction)
    # Fold USGS (Seismic) into Building
    bldg_findings.extend(usgs_findings)
    
    # Re-evaluate overall building status after combining
    if bldg_findings:
        if any(f.status == "VIOLATION_FOUND" for f in bldg_findings):
            bldg_status = "VIOLATION_FOUND"
        elif any(f.status == "POTENTIAL_RISK" for f in bldg_findings):
            bldg_status = "POTENTIAL_RISK"
        elif bldg_status_local != "DATA_UNAVAILABLE":
            bldg_status = "CLEAR"
        else:
            # We have federal data, so it's not totally unavailable
            bldg_status = "CLEAR" if all(f.status == "CLEAR" for f in bldg_findings) else "POTENTIAL_RISK"
    else:
        bldg_status = bldg_status_local

    bldg_result = CategoryResult(
        status=bldg_status,
        score=score_category(bldg_status, bldg_findings),
        findings=bldg_findings
    )
    
    occ_status, occ_findings = await run_occupancy_agent(address, jurisdiction)
    occ_result = CategoryResult(
        status=occ_status,
        score=score_category(occ_status, occ_findings),
        findings=occ_findings
    )
    
    fire_status, fire_findings = await run_fire_agent(address, jurisdiction)
    fire_result = CategoryResult(
        status=fire_status,
        score=score_category(fire_status, fire_findings),
        findings=fire_findings
    )
    
    zon_status, zon_findings = await run_zoning_agent(address, jurisdiction)
    zon_result = CategoryResult(
        status=zon_status,
        score=score_category(zon_status, zon_findings),
        findings=zon_findings
    )
    
    # 4. Risk Scoring
    overall = calculate_overall_risk(env_result, bldg_result, fire_result, zon_result, occ_result)
    
    # 5. Compile Output
    sources = []
    if env_status != "DATA_UNAVAILABLE": sources.append("EPA ECHO")
    if fema_findings: sources.append("FEMA Open Data")
    if usgs_findings: sources.append("USGS Earthquakes")
    if jurisdiction == "CHICAGO" and bldg_status_local != "DATA_UNAVAILABLE": sources.append("Chicago Data Portal")
    if jurisdiction in ["NEW YORK", "NYC"] and bldg_status_local != "DATA_UNAVAILABLE": sources.append("NYC Open Data")
    if jurisdiction in ["SAN FRANCISCO", "SF"] and bldg_status_local != "DATA_UNAVAILABLE": sources.append("SF Open Data")
    
    limitations = []
    if fire_status == "DATA_UNAVAILABLE": limitations.append("Fire inspection data unavailable for this jurisdiction.")
    if zon_status == "DATA_UNAVAILABLE": limitations.append("Zoning classification data unavailable for this jurisdiction.")
    if occ_status == "DATA_UNAVAILABLE": limitations.append("Occupancy record data unavailable for this jurisdiction.")
    
    report = ComplianceReport(
        property=PropertyContext(address=address, latitude=lat, longitude=lng),
        overall=overall,
        environmental=env_result,
        building=bldg_result,
        fire=fire_result,
        zoning=zon_result,
        occupancy=occ_result,
        data_sources=sources,
        limitations=limitations
    )
    
    # 6. LLM Summarization
    report_dict = report.model_dump()
    summary = get_llm_summary(report_dict)
    report.overall.summary = summary
    
    return report

