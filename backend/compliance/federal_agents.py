import httpx
from typing import List, Optional
import logging
from .models import Finding

logger = logging.getLogger(__name__)

async def search_fema_disasters(state: str, county: str) -> List[Finding]:
    """
    Query the FEMA Disaster Declarations API for recent significant events in the county.
    Docs: https://www.fema.gov/openfema-data-page/disaster-declarations-summaries-v2
    """
    findings = []
    if not state or not county:
        return findings

    # FEMA county string format usually expects just the name or "County Name (County)"
    # The Census API returns e.g. "Cook County". The FEMA API uses "Cook (County)" or just "Cook"
    # We will search by state and use a looser search for county if possible.
    # Actually, FEMA API $filter requires exact match, so let's just get the state's recent disasters and filter locally.
    
    url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
    # Get disasters from the last 10 years for the given state
    # Sort descending by declarationDate
    params = {
        "$filter": f"state eq '{state.upper()}'",
        "$orderby": "declarationDate desc",
        "$top": "50"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                declarations = data.get("DisasterDeclarationsSummaries", [])
                
                # Filter down to the specific county if mentioned
                county_upper = county.upper().replace(" COUNTY", "")
                
                matched_declarations = []
                for d in declarations:
                    desig_area = (d.get("designatedArea") or "").upper()
                    if county_upper in desig_area:
                        matched_declarations.append(d)
                
                # Take top 3 most recent
                for d in matched_declarations[:3]:
                    title = d.get("declarationTitle", "Unknown Disaster")
                    date = d.get("declarationDate", "")[:10]
                    incident_type = d.get("incidentType", "Disaster")
                    findings.append(Finding(
                        finding=f"⚠️ FEMA Disaster Declaration: {title} ({incident_type}) on {date} affecting {county}.",
                        source="FEMA Open Data",
                        source_type="government_api",
                        record_id=d.get("disasterNumber", ""),
                        date=date,
                        status="POTENTIAL_RISK",
                        confidence=0.9
                    ))
                
                if not matched_declarations:
                    findings.append(Finding(
                        finding=f"✅ No recent major FEMA disaster declarations found for {county}, {state}.",
                        source="FEMA Open Data",
                        source_type="government_api",
                        status="CLEAR",
                        confidence=0.85
                    ))
            else:
                logger.error(f"[FEMA] API error: {response.status_code}")
    except Exception as e:
        logger.error(f"[FEMA] Error querying disasters: {e}")

    return findings


async def search_usgs_earthquakes(lat: float, lng: float, radius_km: int = 50, min_mag: float = 3.5) -> List[Finding]:
    """
    Query the USGS Earthquake API for recent significant seismic activity.
    Docs: https://earthquake.usgs.gov/fdsnws/event/1/
    """
    findings = []
    if not lat or not lng:
        return findings

    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "latitude": str(lat),
        "longitude": str(lng),
        "maxradiuskm": str(radius_km),
        "minmagnitude": str(min_mag),
        "limit": "5",
        "orderby": "time"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                features = data.get("features", [])
                
                if not features:
                    findings.append(Finding(
                        finding=f"✅ No significant recent seismic activity (Mag >= {min_mag}) within {radius_km}km.",
                        source="USGS Earthquake Hazards",
                        source_type="government_api",
                        status="CLEAR",
                        confidence=0.9
                    ))
                else:
                    for f in features:
                        props = f.get("properties", {})
                        mag = props.get("mag", "Unknown")
                        place = props.get("place", "Unknown location")
                        import datetime
                        time_ms = props.get("time")
                        date_str = ""
                        if time_ms:
                            dt = datetime.datetime.fromtimestamp(time_ms / 1000.0)
                            date_str = dt.strftime("%Y-%m-%d")

                        findings.append(Finding(
                            finding=f"⚠️ Recent Seismic Activity: M{mag} earthquake near {place} on {date_str}.",
                            source="USGS Earthquake Hazards",
                            source_type="government_api",
                            record_id=f.get("id", ""),
                            date=date_str,
                            status="POTENTIAL_RISK",
                            confidence=0.9
                        ))
            else:
                logger.error(f"[USGS] API error: {response.status_code}")
    except Exception as e:
        logger.error(f"[USGS] Error querying earthquakes: {e}")

    return findings
