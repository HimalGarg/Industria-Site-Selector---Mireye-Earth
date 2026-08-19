import argparse
import asyncio
import json
import sys
from agent_council import run_council, CouncilRequest, SiteInput

def parse_site(site_str: str) -> SiteInput:
    """Parse lat,lng,label,cost_usd,area_acres from string.
    Format: lat,lng,label[,cost_usd,area_acres]
    """
    parts = site_str.split(",")
    if len(parts) < 3:
        raise ValueError(f"Site string '{site_str}' must have at least lat,lng,label")
    
    try:
        lat = float(parts[0])
        lng = float(parts[1])
        label = parts[2]
        
        cost_usd = None
        area_acres = None
        
        if len(parts) >= 4 and parts[3].strip():
            cost_usd = float(parts[3])
        if len(parts) >= 5 and parts[4].strip():
            area_acres = float(parts[4])
            
        return SiteInput(
            lat=lat, 
            lng=lng, 
            label=label, 
            cost_usd=cost_usd, 
            area_acres=area_acres
        )
    except ValueError as e:
        raise ValueError(f"Error parsing site string '{site_str}': {e}")

async def main():
    parser = argparse.ArgumentParser(description="Run the AgentCouncil Site Ranker")
    parser.add_argument(
        "--sites", 
        nargs="+", 
        required=True, 
        help="List of sites in format lat,lng,label[,cost_usd,area_acres]"
    )
    parser.add_argument(
        "--worker-profile", 
        type=str, 
        help="Optional unstructured description of the worker day-in-the-life",
        default=None
    )
    parser.add_argument(
        "--output", 
        type=str, 
        help="Optional output JSON file path",
        default=None
    )
    
    args = parser.parse_args()
    
    try:
        sites = [parse_site(s) for s in args.sites]
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    request = CouncilRequest(
        sites=sites,
        worker_profile=args.worker_profile
    )
    
    print(f"Starting council evaluation for {len(sites)} sites...")
    response = await run_council(request)
    
    # Dump to JSON
    json_out = response.model_dump_json(indent=2)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(json_out)
        print(f"Success! Output written to {args.output}")
    else:
        print("\n--- FINAL RANKING ---\n")
        print(json_out)

if __name__ == "__main__":
    # Setup basic logging
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    asyncio.run(main())
