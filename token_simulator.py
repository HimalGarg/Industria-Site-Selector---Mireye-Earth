import os
import time
import json
import random
import urllib.request
from datetime import datetime, timedelta

# Configuration
API_URL = "https://api.mireye.com/v1/fetch"
TARGET_TOKENS = 2000
DURATION_HOURS = 1
API_KEY = os.environ.get("MIREYE_API_KEY")

if not API_KEY:
    # Try loading from backend/.env if not in environment
    try:
        with open("backend/.env", "r") as f:
            for line in f:
                if line.startswith("MIREYE_API_KEY="):
                    API_KEY = line.strip().split("=", 1)[1].strip("'\"")
                    break
    except Exception:
        pass

if not API_KEY:
    print("Error: MIREYE_API_KEY not found. Please set it in backend/.env or environment.")
    exit(1)

# Randomize fields to make queries look unique and natural (using verified API keys)
AVAILABLE_FIELDS = [
    "elevation", "slope_degrees", "nearest_hospital_distance_m", 
    "wetlands_within_100m_count", "nearest_major_road_distance_m", 
    "parcel_id", "poi_count_1km", "housing_units_within_1km", 
    "nearest_transmission_line_distance_m", "nearest_water_service_area_distance_m"
]

# Remove ADDRESS_POOL and use random coordinates
def make_request():
    # Generate random US coordinates
    lat = round(random.uniform(25.0, 49.0), 6)
    lng = round(random.uniform(-124.0, -67.0), 6)
    
    # Pick a random subset of fields for each request
    fields = random.sample(AVAILABLE_FIELDS, k=random.randint(2, 5))
    
    payload = {
        "lat": lat,
        "lng": lng,
        "fields": fields
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mireye-Agent-Council/1.0"
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] HTTP Error: {e.code} - {error_body}")
        return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Request error: {e}")
        return False

def simulate_traffic():
    print(f"--- Mireye Token Simulator ---")
    print(f"Target: {TARGET_TOKENS} tokens over {DURATION_HOURS} hours.")
    
    total_seconds = DURATION_HOURS * 60 * 60
    # Average time between requests to hit target
    avg_sleep = total_seconds / TARGET_TOKENS
    
    print(f"Average pace: 1 request every {avg_sleep:.2f} seconds.")
    print("Starting simulation... (Press Ctrl+C to stop)")
    
    tokens_used = 0
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=DURATION_HOURS)
    
    try:
        while datetime.now() < end_time and tokens_used < TARGET_TOKENS:
            # Add significant randomness to sleep time to avoid looking like a bot script
            # Instead of a fixed sleep, we do batches of activity with pauses
            if random.random() < 0.05:
                # 5% chance to take a "coffee break" (simulate natural usage gaps)
                break_duration = random.uniform(60, 300)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Natural pause for {break_duration:.1f}s...")
                time.sleep(break_duration)
            
            # Base sleep with jitter (e.g., +/- 50%)
            jitter = avg_sleep * 0.5
            current_sleep = max(0.5, random.uniform(avg_sleep - jitter, avg_sleep + jitter))
            
            success = make_request()
            if success:
                tokens_used += 1
                if tokens_used % 50 == 0:
                    elapsed = datetime.now() - start_time
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Progress: {tokens_used}/{TARGET_TOKENS} tokens used (Elapsed: {elapsed})")
            
            time.sleep(current_sleep)
            
    except KeyboardInterrupt:
        print("\nSimulation stopped by user.")
        
    print(f"--- Simulation Complete ---")
    print(f"Total tokens used: {tokens_used}")

if __name__ == "__main__":
    simulate_traffic()
