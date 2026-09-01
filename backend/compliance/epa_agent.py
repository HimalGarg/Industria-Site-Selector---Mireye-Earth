import httpx
from typing import List
from .models import Finding
import logging

logger = logging.getLogger(__name__)


async def search_epa_facilities(lat: float, lng: float, radius_miles: float = 1.0) -> List[Finding]:
    """
    Query EPA ECHO facility search API by spatial coordinates.

    EPA ECHO uses a two-step process:
      1. GET get_facilities → returns QueryID + summary row counts
      2. GET get_qid       → fetches paginated facility records using QueryID

    Docs: https://echo.epa.gov/tools/web-services/facility-search-all-data
    """
    step1_url = "https://echodata.epa.gov/echo/echo_rest_services.get_facilities"
    step1_params = {
        "output": "JSON",
        "p_lat": str(lat),
        "p_long": str(lng),
        "p_radius": str(radius_miles),
    }

    findings = []
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # ── Step 1: Get QueryID ───────────────────────────────────────────
            r1 = await client.get(step1_url, params=step1_params)
            logger.info(f"[EPA ECHO] Step1 status={r1.status_code} lat={lat} lng={lng} r={radius_miles}mi")

            if r1.status_code != 200:
                logger.error(f"[EPA ECHO] Step1 failed: {r1.status_code}")
                return findings

            data1 = r1.json()
            results1 = data1.get("Results", {})
            query_id = results1.get("QueryID")
            query_rows = int(results1.get("QueryRows", 0) or 0)

            logger.info(f"[EPA ECHO] QueryID={query_id}, total facilities={query_rows}")

            if not query_id or query_rows == 0:
                logger.info("[EPA ECHO] No facilities found in radius.")
                return findings

            # ── Step 2: Fetch Facility Records via QueryID ───────────────────
            step2_url = "https://echodata.epa.gov/echo/echo_rest_services.get_qid"
            step2_params = {
                "output": "JSON",
                "qid": str(query_id),
                "responseset": "25",    # Fetch up to 25 facilities
                "p_qnc": "0",          # All facilities regardless of compliance
            }

            r2 = await client.get(step2_url, params=step2_params)
            logger.info(f"[EPA ECHO] Step2 status={r2.status_code} qid={query_id}")

            if r2.status_code != 200:
                logger.error(f"[EPA ECHO] Step2 get_qid failed: {r2.status_code}: {r2.text[:200]}")
                return findings

            data2 = r2.json()
            results2 = data2.get("Results", {})
            facilities = results2.get("Facilities", [])

            logger.info(f"[EPA ECHO] Retrieved {len(facilities)} facility records.")

            if not facilities:
                return findings

            for fac in facilities:
                fac_name = fac.get("FacName", "Unknown Facility")
                fac_id = fac.get("RegistryID", "")
                fac_street = fac.get("FacStreet", "")
                fac_city = fac.get("FacCity", "")
                location_str = ", ".join(filter(None, [fac_street, fac_city]))

                # Key compliance signals
                snc_flag = str(fac.get("FacDerivedStsSNCFlag", "N")).strip().upper()
                try:
                    nc_qtrs = int(fac.get("FacQtrsWithNC", 0) or 0)
                except (ValueError, TypeError):
                    nc_qtrs = 0
                try:
                    penalty_count = int(fac.get("FacPenaltyCount", 0) or 0)
                except (ValueError, TypeError):
                    penalty_count = 0

                if snc_flag == "Y":
                    findings.append(Finding(
                        finding=(
                            f"Significant Non-Compliance (SNC) at nearby facility: {fac_name}"
                            + (f" ({location_str})" if location_str else "")
                            + ". Active SNC status in EPA ECHO."
                        ),
                        source="EPA ECHO",
                        source_type="government_api",
                        record_id=fac_id,
                        status="VIOLATION_FOUND",
                        confidence=0.90,
                    ))
                elif nc_qtrs > 0:
                    findings.append(Finding(
                        finding=(
                            f"Non-compliance history at nearby facility: {fac_name}"
                            + (f" ({location_str})" if location_str else "")
                            + f". {nc_qtrs} quarter(s) of non-compliance recorded in EPA ECHO."
                        ),
                        source="EPA ECHO",
                        source_type="government_api",
                        record_id=fac_id,
                        status="POTENTIAL_RISK",
                        confidence=0.80,
                    ))
                elif penalty_count > 0:
                    findings.append(Finding(
                        finding=(
                            f"Enforcement history at nearby facility: {fac_name}"
                            + (f" ({location_str})" if location_str else "")
                            + f". {penalty_count} EPA penalty action(s) on record."
                        ),
                        source="EPA ECHO",
                        source_type="government_api",
                        record_id=fac_id,
                        status="POTENTIAL_RISK",
                        confidence=0.75,
                    ))
                else:
                    findings.append(Finding(
                        finding=(
                            f"EPA Regulated Facility nearby: {fac_name}"
                            + (f" ({location_str})" if location_str else "")
                            + ". No significant violations currently reported."
                        ),
                        source="EPA ECHO",
                        source_type="government_api",
                        record_id=fac_id,
                        status="CLEAR",
                        confidence=0.85,
                    ))

    except httpx.TimeoutException:
        logger.error(f"[EPA ECHO] Request timed out for lat={lat}, lng={lng}")
    except Exception as e:
        logger.error(f"[EPA ECHO] Unexpected error: {e}")

    return findings
