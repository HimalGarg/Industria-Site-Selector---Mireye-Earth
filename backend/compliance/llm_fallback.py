import os
from openai import OpenAI
from typing import List, Tuple
import logging
from .models import Finding

logger = logging.getLogger(__name__)

def run_llm_compliance_fallback(address: str, jurisdiction: str, category: str) -> Tuple[str, List[Finding]]:
    """
    If municipal open data APIs are unavailable for a given jurisdiction, 
    use an LLM to generate a contextual regulatory/compliance baseline.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return "DATA_UNAVAILABLE", [Finding(
            finding="Data unavailable for this municipality and no LLM key provided for AI fallback.",
            source="System", source_type="unavailable", status="UNKNOWN"
        )]
        
    try:
        client = OpenAI(api_key=api_key)
        model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        
        prompt = f"""
        You are an expert Commercial Real Estate Regulatory and Compliance Analyst.
        We are doing due diligence on the property at: {address} (Jurisdiction: {jurisdiction}).
        
        We lack direct API access to the local government database for the category: {category.upper()}.
        Please provide 1-2 highly specific, realistic baseline compliance findings for this category in this jurisdiction.
        Include typical local ordinances, expected requirements, or known historical zoning/fire/environmental rules in this area.
        Format your response as a clear bulleted list (itemized points). Keep it concise and professional.
        """
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
            max_tokens=1024
        )
        
        ai_text = response.choices[0].message.content.strip()
        
        return "REQUIRES_MANUAL_REVIEW", [Finding(
            finding=f"AI Regulatory Context: {ai_text}",
            source=f"OpenAI {model_name} Knowledge Base",
            source_type="llm_agent",
            status="REQUIRES_MANUAL_REVIEW",
            confidence=0.5
        )]
        
    except Exception as e:
        logger.error(f"LLM Fallback failed: {e}")
        return "DATA_UNAVAILABLE", [Finding(
            finding=f"LLM Fallback query failed.",
            source="LLM", source_type="unavailable", status="UNKNOWN"
        )]
