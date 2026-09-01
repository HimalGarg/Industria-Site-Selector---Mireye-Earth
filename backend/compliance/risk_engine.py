from .models import CategoryResult, Finding, OverallResult
from typing import List

def score_environmental(findings: List[Finding]) -> int:
    score = 100
    for f in findings:
        if f.status == "VIOLATION_FOUND":
            score -= 35
        elif f.status == "POTENTIAL_RISK":
            score -= 15
    return max(0, score)

def score_category(status: str, findings: List[Finding]) -> int:
    if status == "DATA_UNAVAILABLE":
        return None
    if status == "DATA_NOT_FOUND" or status == "CLEAR":
        return 100
        
    score = 100
    for f in findings:
        if f.status == "VIOLATION_FOUND":
            score -= 35
        elif f.status == "POTENTIAL_RISK":
            score -= 15
        elif f.status == "REQUIRES_MANUAL_REVIEW":
            score -= 20
    return max(0, score)

def calculate_overall_risk(env_result: CategoryResult, bldg_result: CategoryResult,
                           fire_result: CategoryResult, zon_result: CategoryResult,
                           occ_result: CategoryResult) -> OverallResult:
    
    # Weights based on specs
    weights = {
        "environmental": 0.30,
        "zoning": 0.25,
        "building": 0.20,
        "occupancy": 0.15,
        "fire": 0.10
    }
    
    results = {
        "environmental": env_result,
        "building": bldg_result,
        "fire": fire_result,
        "zoning": zon_result,
        "occupancy": occ_result
    }
    
    total_weighted_score = 0
    total_confidence = 0
    available_weight_sum = 0
    
    for cat, res in results.items():
        weight = weights[cat]
        if res.status != "DATA_UNAVAILABLE":
            total_confidence += weight * 100
            if res.score is not None:
                total_weighted_score += res.score * weight
                available_weight_sum += weight
        
    # Scale score if some categories were unavailable
    final_score = int(total_weighted_score / available_weight_sum) if available_weight_sum > 0 else 0
    final_confidence = int(total_confidence)
    
    if final_score >= 80:
        overall_risk = "LOW"
    elif final_score >= 60:
        overall_risk = "MEDIUM"
    else:
        overall_risk = "HIGH"
        
    # Override risk if confidence is extremely low
    if final_confidence < 30:
        overall_risk = "REQUIRES_MANUAL_REVIEW"
        
    return OverallResult(
        risk=overall_risk,
        score=final_score,
        confidence=final_confidence
    )
