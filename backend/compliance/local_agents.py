import httpx
from .llm_fallback import run_llm_compliance_fallback
from typing import List, Tuple, Optional
from .models import Finding
import logging
import urllib.parse
import re

logger = logging.getLogger(__name__)

import pandas as pd
import os


def _clean_part(part: str) -> str:
    """Strip trailing commas, periods, and other punctuation from an address token."""
    return part.strip().rstrip(",.;:'\"").strip()


def _parse_address_parts(address: str) -> Tuple[str, str]:
    """
    Parse a raw property address into (street_number, street_name).

    Handles formats like:
      - "9016 S Halsted St, Chicago, IL 60620"
      - "1800 2nd Loop Rd, Florence, SC 29501"
      - "9016 S HALSTED STREET"
    Returns (street_number, street_name) both as uppercase strings.
    """
    DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW", "NORTH", "SOUTH", "EAST", "WEST"}
    STREET_TYPES = {
        "AVE", "AVENUE", "ST", "STREET", "BLVD", "BOULEVARD",
        "RD", "ROAD", "DR", "DRIVE", "PL", "PLACE", "CT", "COURT",
        "LN", "LANE", "WAY", "LOOP", "HWY", "HIGHWAY", "PKWY",
        "PARKWAY", "TER", "TERRACE", "CIR", "CIRCLE", "SQ", "SQUARE"
    }

    # Only use the first segment (before the first comma) to avoid city/state noise
    first_segment = address.split(",")[0].strip().upper()
    parts = first_segment.split()

    if len(parts) < 2:
        return parts[0] if parts else "", ""

    street_number = _clean_part(parts[0])
    street_name = ""

    # Skip directionals (N, S, E, W) — they precede the actual street name
    for part in parts[1:]:
        cleaned = _clean_part(part)
        if cleaned in DIRECTIONALS:
            continue
        if cleaned in STREET_TYPES:
            # If we haven't found a name yet, use this as a last resort
            if not street_name:
                street_name = cleaned
            break
        street_name = cleaned
        break

    # Final fallback: use the second token (after cleaning)
    if not street_name and len(parts) > 1:
        street_name = _clean_part(parts[1])

    return street_number, street_name


async def search_chicago_permits(address: str, street_number: str, street_name: str) -> Optional[List[Finding]]:
    findings = []

    # Check for local CSV dataset first (blazingly fast offline access)
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    permits_csv = os.path.join(data_dir, "permits.csv")

    if os.path.exists(permits_csv):
        try:
            df = pd.read_csv(
                permits_csv,
                usecols=["PERMIT#", "PERMIT_TYPE", "ISSUE_DATE", "WORK_DESCRIPTION",
                         "STREET_NUMBER", "STREET_NAME", "CURRENT_STATUS"],
                dtype=str
            )
            df = df.fillna("")
            street_name_upper = street_name.upper()
            street_number_str = str(street_number)

            matches = df[
                (df["STREET_NUMBER"] == street_number_str) &
                (df["STREET_NAME"].str.contains(street_name_upper, case=False, na=False))
            ]
            matches = matches.head(10)

            for _, permit in matches.iterrows():
                permit_type = permit.get("PERMIT_TYPE", "Unknown")
                issue_date = str(permit.get("ISSUE_DATE", ""))[:10]
                work_desc = str(permit.get("WORK_DESCRIPTION", ""))
                current_status = str(permit.get("CURRENT_STATUS", ""))

                is_demolition = "WRECKING" in permit_type.upper() or "DEMOLITION" in work_desc.upper()
                status = "POTENTIAL_RISK" if is_demolition else "CLEAR"

                if is_demolition:
                    finding_str = f"⚠️ Demolition/Wrecking permit found: {permit_type} (issued {issue_date}). Status: {current_status}."
                else:
                    finding_str = f"📋 {permit_type} permit issued {issue_date}. Status: {current_status}."

                findings.append(Finding(
                    finding=finding_str,
                    source="Chicago Open Data (Local CSV)",
                    source_type="document",
                    record_id=permit.get("PERMIT#"),
                    date=issue_date,
                    status=status,
                    confidence=0.95
                ))
            return findings
        except Exception as e:
            logger.error(f"Local Chicago Permits CSV Error: {e}")
            return None

    # Fallback: Socrata API (Chicago Open Data Portal — no auth required for public data)
    url = "https://data.cityofchicago.org/resource/ydr8-5enu.json"
    query = f"street_number='{street_number}' AND upper(street_name) LIKE '%{street_name.upper()}%'"
    params = {"$where": query, "$limit": 10, "$order": "issue_date DESC"}
    headers = {"User-Agent": "Mozilla/5.0 MireyeComplianceAgent/1.0"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                for permit in response.json():
                    permit_type = permit.get("permit_type", "Unknown")
                    issue_date = permit.get("issue_date", "")[:10]
                    work_desc = permit.get("work_description", "")
                    status = "POTENTIAL_RISK" if ("WRECKING" in permit_type or "DEMOLITION" in work_desc.upper()) else "CLEAR"
                    findings.append(Finding(
                        finding=f"📋 {permit_type} permit issued {issue_date}." if status == "CLEAR" else f"⚠️ Demolition permit found ({issue_date}).",
                        source="Chicago Data Portal",
                        source_type="government_api",
                        record_id=permit.get("permit_"),
                        date=issue_date,
                        status=status,
                        confidence=0.9
                    ))
                return findings
            else:
                logger.error(f"Chicago Permits API Error {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Chicago Permits API Error: {e}")
        return None


async def search_chicago_violations(
    address: str, street_number: str, street_name: str, category_keyword: str
) -> Optional[List[Finding]]:
    findings = []
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    violations_csv = os.path.join(data_dir, "violations.csv")

    if os.path.exists(violations_csv):
        try:
            import csv
            with open(violations_csv, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = [h.upper().strip() for h in next(reader)]

            usecols = [
                h for h in headers
                if any(kw in h for kw in ["STREET", "DATE", "DESC", "CODE", "STATUS", "ID", "VIOLATION"])
            ]
            df = pd.read_csv(violations_csv, usecols=usecols, dtype=str)
            df = df.fillna("")

            # Dynamically map column names
            street_num_col = next((c for c in df.columns if "STREET_NUMBER" in c), None)
            if not street_num_col:
                street_num_col = next((c for c in df.columns if "ADDRESS" in c), None)

            street_name_col = next((c for c in df.columns if "STREET_NAME" in c), None)
            if not street_name_col:
                street_name_col = street_num_col  # fallback to same ADDRESS column

            desc_col = next((c for c in df.columns if "VIOLATION_DESCRIPTION" in c or "DESC" in c), None)
            date_col = next((c for c in df.columns if "DATE" in c), None)
            status_col = next((c for c in df.columns if "STATUS" in c), None)

            if not street_num_col:
                return []

            street_number_str = str(street_number)
            street_name_upper = street_name.upper()

            if street_num_col == street_name_col:
                matches = df[
                    df[street_num_col].str.contains(street_number_str, na=False) &
                    df[street_num_col].str.contains(street_name_upper, case=False, na=False)
                ]
            else:
                matches = df[
                    (df[street_num_col] == street_number_str) &
                    (df[street_name_col].str.contains(street_name_upper, case=False, na=False))
                ]

            if desc_col and category_keyword:
                matches = matches[matches[desc_col].str.contains(category_keyword, case=False, na=False)]

            matches = matches.head(10)

            for _, row in matches.iterrows():
                desc = ""
                if desc_col:
                    raw_desc = str(row.get(desc_col, ""))
                    desc = (raw_desc[:100] + "...") if len(raw_desc) > 100 else raw_desc

                date = str(row.get(date_col, ""))[:10] if date_col else ""
                v_status = str(row.get(status_col, "OPEN")) if status_col else "OPEN"
                status = "POTENTIAL_RISK" if v_status.upper() not in ["COMPLIED", "CLOSED", "NO ENTRY"] else "CLEAR"

                findings.append(Finding(
                    finding=f"[{v_status}] {desc} ({date})" if desc else f"Violation record ({date}) — status: {v_status}",
                    source="Chicago Open Data (Local CSV)",
                    source_type="document",
                    record_id="",
                    date=date,
                    status=status,
                    confidence=0.95
                ))
            return findings

        except Exception as e:
            logger.error(f"Local Chicago Violations CSV Error: {e}")
            return None

    return None


async def search_nyc_permits(address: str, street_number: str, street_name: str) -> Optional[List[Finding]]:
    url = "https://data.cityofnewyork.us/resource/ipu4-2q9a.json"
    query = f"house__='{street_number}' AND upper(street_name) LIKE '%{street_name.upper()}%'"
    params = {"$where": query, "$limit": 10, "$order": "issuance_date DESC"}
    headers = {"User-Agent": "Mozilla/5.0 MireyeComplianceAgent/1.0"}
    findings = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                for permit in response.json():
                    permit_type = permit.get("permit_type", "Unknown")
                    issue_date = permit.get("issuance_date", "")[:10]
                    work_desc = permit.get("job_description", "")
                    status = "POTENTIAL_RISK" if ("DEMOLITION" in work_desc.upper() or permit_type == "DM") else "CLEAR"
                    findings.append(Finding(
                        finding=f"⚠️ Demolition permit ({issue_date})." if status == "POTENTIAL_RISK" else f"📋 Permit Type: {permit_type} ({issue_date}).",
                        source="NYC Open Data",
                        source_type="government_api",
                        record_id=permit.get("job_doc___"),
                        date=issue_date,
                        status=status,
                        confidence=0.9
                    ))
                return findings
            else:
                logger.error(f"NYC Permits Error {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"NYC Permits Error: {e}")
        return None


async def search_sf_permits(address: str, street_number: str, street_name: str) -> Optional[List[Finding]]:
    url = "https://data.sfgov.org/resource/i98e-dpeg.json"
    query = f"street_number='{street_number}' AND upper(street_name) LIKE '%{street_name.upper()}%'"
    params = {"$where": query, "$limit": 10, "$order": "permit_creation_date DESC"}
    headers = {"User-Agent": "Mozilla/5.0 MireyeComplianceAgent/1.0"}
    findings = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                for permit in response.json():
                    permit_type = permit.get("permit_type", "Unknown")
                    issue_date = permit.get("permit_creation_date", "")[:10]
                    work_desc = permit.get("description", "")
                    status = "POTENTIAL_RISK" if "DEMOLITION" in work_desc.upper() else "CLEAR"
                    findings.append(Finding(
                        finding=f"⚠️ Demolition permit ({issue_date})." if status == "POTENTIAL_RISK" else f"📋 Permit: {permit_type} ({issue_date}).",
                        source="SF Open Data",
                        source_type="government_api",
                        record_id=permit.get("permit_number"),
                        date=issue_date,
                        status=status,
                        confidence=0.9
                    ))
                return findings
            else:
                logger.error(f"SF Permits Error {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"SF Permits Error: {e}")
        return None


async def run_building_agent(address: str, jurisdiction: str) -> Tuple[str, List[Finding]]:
    street_number, street_name = _parse_address_parts(address)

    if not street_number or not street_name:
        return "DATA_NOT_FOUND", [Finding(
            finding="⚠️ Could not parse street number/name from address.",
            source="System", source_type="unavailable", status="UNKNOWN"
        )]

    if jurisdiction == "CHICAGO":
        findings = await search_chicago_permits(address, street_number, street_name)
    elif jurisdiction in ("NEW YORK", "NYC"):
        findings = await search_nyc_permits(address, street_number, street_name)
    elif jurisdiction in ("SAN FRANCISCO", "SF"):
        findings = await search_sf_permits(address, street_number, street_name)
    else:
        return run_llm_compliance_fallback(address, jurisdiction, "Building Permits")

    if findings is None:
        return run_llm_compliance_fallback(address, jurisdiction, "Occupancy & Certificates")


async def run_fire_agent(address: str, jurisdiction: str) -> Tuple[str, List[Finding]]:
    street_number, street_name = _parse_address_parts(address)

    if jurisdiction == "CHICAGO" and street_number and street_name:
        findings = await search_chicago_violations(address, street_number, street_name, "FIRE")
        if findings is not None:
            if not findings:
                return "CLEAR", [Finding(
                    finding="✅ No fire code violations found in local dataset.",
                    source="Chicago Open Data (Local CSV)", source_type="document", status="CLEAR"
                )]
            risk = "POTENTIAL_RISK" if any(f.status == "POTENTIAL_RISK" for f in findings) else "CLEAR"
            return risk, findings

    return run_llm_compliance_fallback(address, jurisdiction, "Fire Safety Codes")


async def run_zoning_agent(address: str, jurisdiction: str) -> Tuple[str, List[Finding]]:
    street_number, street_name = _parse_address_parts(address)

    if jurisdiction == "CHICAGO" and street_number and street_name:
        findings = await search_chicago_violations(address, street_number, street_name, "ZONING")
        if findings is not None:
            if not findings:
                return "CLEAR", [Finding(
                    finding="✅ No zoning violations found in local dataset.",
                    source="Chicago Open Data (Local CSV)", source_type="document", status="CLEAR"
                )]
            risk = "POTENTIAL_RISK" if any(f.status == "POTENTIAL_RISK" for f in findings) else "CLEAR"
            return risk, findings

    return run_llm_compliance_fallback(address, jurisdiction, "Zoning & Land Use")
