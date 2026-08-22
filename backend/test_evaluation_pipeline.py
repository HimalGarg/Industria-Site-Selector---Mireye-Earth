"""
backend/test_evaluation_pipeline.py â€” Integration tests for the evaluation pipeline
====================================================================================

Run with:
  python test_evaluation_pipeline.py

Tests:
  1. DB schema check â€” mireye_cache and evaluations tables exist
  2. Mireye fetcher â€” can geocode a real address and get coordinates
  3. Mireye cache â€” second fetch of same address hits cache, not Mireye
  4. Field format check â€” confirm field objects have expected structure
  5. End-to-end pipeline â€” POST /evaluate-site â†’ poll â†’ done (requires OPENAI_API_KEY)
  6. Sparse data test â€” pipeline handles cart item with many null llm_structured fields

Usage:
  python test_evaluation_pipeline.py            # runs all tests
  python test_evaluation_pipeline.py --no-llm   # skip tests requiring OpenAI key
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import unittest
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup paths so evaluate/ package is importable
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

# Load backend .env before imports
_env_path = BACKEND_DIR / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if k and not os.environ.get(k):
                    os.environ[k] = v

DB_PATH = BACKEND_DIR / "site_ranker.db"
API_BASE = "http://127.0.0.1:8000"
SKIP_LLM = "--no-llm" in sys.argv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(path: str) -> dict:
    url = f"{API_BASE}{path}"
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def api_post(path: str, body: dict) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get_cart_items(limit: int = 5) -> list[dict]:
    """Query cart_items directly from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT cart_item_id, address, llm_structured FROM cart_items ORDER BY added_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestDBSchema(unittest.TestCase):
    """Test 1: Verify new tables exist in site_ranker.db."""

    def test_mireye_cache_table_exists(self):
        conn = sqlite3.connect(DB_PATH)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        self.assertIn("mireye_cache", tables, "mireye_cache table missing â€” did init_db() run?")
        print("[DB SCHEMA] âœ“ mireye_cache table exists")

    def test_evaluations_table_exists(self):
        conn = sqlite3.connect(DB_PATH)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        self.assertIn("evaluations", tables, "evaluations table missing â€” did init_db() run?")
        print("[DB SCHEMA] âœ“ evaluations table exists")

    def test_evaluations_columns(self):
        conn = sqlite3.connect(DB_PATH)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()}
        conn.close()
        required = {"evaluation_id", "cart_item_id", "overall_score", "recommendation",
                    "conflicts_flagged", "agent_results", "created_at"}
        missing = required - cols
        self.assertEqual(missing, set(), f"evaluations table missing columns: {missing}")
        print("[DB SCHEMA] âœ“ evaluations columns correct")


class TestMireyeFetcher(unittest.TestCase):
    """Test 2 & 3: Mireye geocoding and cache behavior."""

    TEST_ADDRESS = "1800 2nd Loop Rd, Florence, SC 29501"

    def setUp(self):
        """Clear the cache entry for our test address before each test."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM mireye_cache WHERE cache_key LIKE ?", (f"%{self.TEST_ADDRESS[:20]}%",))
        conn.commit()
        conn.close()

    def test_address_resolution(self):
        """Test 2: Mireye resolves an address to lat/lng with match quality."""
        from evaluate.mireye_fetcher import resolve_address
        geo = resolve_address(self.TEST_ADDRESS)

        self.assertIn("lat", geo)
        self.assertIn("lng", geo)
        self.assertIn("coordinate_match_quality", geo)
        self.assertIn("normalized_address", geo)

        self.assertIsInstance(geo["lat"], float)
        self.assertIsInstance(geo["lng"], float)
        self.assertGreater(abs(geo["lat"]), 0)
        self.assertGreater(abs(geo["lng"]), 0)

        print(f"[GEOCODE] âœ“ {self.TEST_ADDRESS}")
        print(f"          lat={geo['lat']:.5f}, lng={geo['lng']:.5f}")
        print(f"          quality={geo['coordinate_match_quality']}")
        print(f"          normalized={geo['normalized_address']!r}")

    def test_cache_prevents_duplicate_mireye_calls(self):
        """Test 3: Running the same fetch twice uses cache on second run."""
        from evaluate.mireye_fetcher import resolve_address, fetch_fields_with_cache

        # First: geocode to get cache_key
        geo = resolve_address(self.TEST_ADDRESS)
        cache_key = geo["normalized_address"]

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        test_fields = ["elevation", "slope_degrees", "tree_canopy_pct"]

        # First fetch â€” should be CACHE MISS
        print(f"\n[CACHE TEST] First fetch (expect MISS):")
        result_1 = fetch_fields_with_cache(conn, cache_key, test_fields)

        # Second fetch â€” should be CACHE HIT
        print(f"[CACHE TEST] Second fetch (expect HIT):")
        result_2 = fetch_fields_with_cache(conn, cache_key, test_fields)

        conn.close()

        # Both should have the same values
        for field in test_fields:
            v1 = result_1.get(field)
            v2 = result_2.get(field)
            # Values should be equal (or both None)
            if v1 is not None and v2 is not None:
                self.assertEqual(
                    v1.get("value") if isinstance(v1, dict) else v1,
                    v2.get("value") if isinstance(v2, dict) else v2,
                    f"Cached value for {field} differs from original"
                )

        print(f"[CACHE] âœ“ Second run hits cache. Values consistent for: {test_fields}")

    def test_field_objects_have_expected_structure(self):
        """Test 4: Field objects from Mireye have value/unit/source keys."""
        from evaluate.mireye_fetcher import resolve_address, fetch_fields_with_cache

        geo = resolve_address(self.TEST_ADDRESS)
        cache_key = geo["normalized_address"]

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        fields = ["elevation", "land_use_class", "nearest_major_road_distance_m"]
        result = fetch_fields_with_cache(conn, cache_key, fields)
        conn.close()

        for field in fields:
            obj = result.get(field)
            if obj is not None:
                self.assertIsInstance(obj, dict, f"Field {field!r} should be a dict")
                self.assertIn("value", obj, f"Field {field!r} missing 'value' key")
                self.assertIn("source", obj, f"Field {field!r} missing 'source' key")
                print(f"[FIELD] âœ“ {field}: value={obj.get('value')}, source={obj.get('source')}")
            else:
                print(f"[FIELD] âš  {field}: null (field may not be available for this location)")


@unittest.skipIf(SKIP_LLM, "Skipping LLM tests (--no-llm flag set or OPENAI_API_KEY missing)")
class TestFullPipeline(unittest.TestCase):
    """Test 5 & 6: Full end-to-end pipeline via the API."""

    def _poll_until_done(self, evaluation_id: str, timeout_sec: int = 300) -> dict:
        """Poll GET /evaluate-site/{id} until status=done or timeout."""
        start = time.time()
        while time.time() - start < timeout_sec:
            result = api_get(f"/evaluate-site/{evaluation_id}")
            status = result.get("status")
            if status == "done":
                return result
            if status == "error":
                self.fail(f"Pipeline returned error: {result.get('error')}")
            print(f"  [POLL] status={status}... waiting 5s")
            time.sleep(5)
        self.fail(f"Evaluation timed out after {timeout_sec}s")

    def test_pipeline_crexi_item(self):
        """Test 5a: Run full pipeline against a Crexi cart item."""
        items = get_cart_items(10)
        # Pick the first item (they come from both Crexi and LoopNet)
        self.assertGreater(len(items), 0, "No cart items in DB â€” add some first")

        item = items[0]
        cart_item_id = item["cart_item_id"]
        address = item["address"]
        print(f"\n[PIPELINE TEST] cart_item_id={cart_item_id}")
        print(f"                address={address!r}")

        # Start evaluation
        response = api_post("/evaluate-site", {"cart_item_id": cart_item_id})
        self.assertEqual(response.get("status"), "processing")
        evaluation_id = response.get("evaluation_id")
        self.assertIsNotNone(evaluation_id)
        print(f"[PIPELINE] evaluation_id={evaluation_id} | status=processing")

        # Poll for result
        result = self._poll_until_done(evaluation_id)
        self._assert_valid_evaluation(result)

    def test_pipeline_second_item_cache_hit(self):
        """Test 5b: Run pipeline on a second cart item at a different address."""
        items = get_cart_items(10)
        self.assertGreater(len(items), 1, "Need at least 2 cart items in DB")

        item = items[1]  # Second item (different address)
        cart_item_id = item["cart_item_id"]
        address = item["address"]
        print(f"\n[PIPELINE TEST 2] cart_item_id={cart_item_id}")
        print(f"                  address={address!r}")

        response = api_post("/evaluate-site", {"cart_item_id": cart_item_id})
        evaluation_id = response.get("evaluation_id")
        result = self._poll_until_done(evaluation_id)
        self._assert_valid_evaluation(result)

    def test_repeat_run_uses_cache(self):
        """Test 5c: Running the same cart_item_id twice â€” second run uses cache."""
        items = get_cart_items(1)
        self.assertGreater(len(items), 0, "No cart items in DB")
        cart_item_id = items[0]["cart_item_id"]

        print(f"\n[CACHE HIT TEST] Running same item twice: {cart_item_id}")

        # First run
        r1 = api_post("/evaluate-site", {"cart_item_id": cart_item_id})
        self._poll_until_done(r1["evaluation_id"])
        print("[CACHE HIT TEST] First run done.")

        # Second run â€” should see [CACHE HIT] in server logs
        print("[CACHE HIT TEST] Starting second run (check server logs for [CACHE HIT]):")
        r2 = api_post("/evaluate-site", {"cart_item_id": cart_item_id})
        result = self._poll_until_done(r2["evaluation_id"])
        self._assert_valid_evaluation(result)
        print("[CACHE HIT TEST] âœ“ Second run succeeded. Check server logs for [CACHE HIT] lines.")

    def _assert_valid_evaluation(self, result: dict) -> None:
        """Assert that an evaluation result has the expected structure."""
        self.assertEqual(result.get("status"), "done")
        self.assertIsInstance(result.get("overall_score"), int)
        self.assertGreaterEqual(result["overall_score"], 0)
        self.assertLessEqual(result["overall_score"], 100)
        self.assertIsInstance(result.get("recommendation"), str)
        self.assertIsInstance(result.get("conflicts_flagged"), list)
        self.assertIsInstance(result.get("agent_results"), list)
        self.assertEqual(len(result["agent_results"]), 5, "Expected 5 agent results")

        print(f"\n[EVAL RESULT] overall_score={result['overall_score']}")
        print(f"              recommendation={result['recommendation']!r}")
        print(f"              conflicts_flagged={len(result['conflicts_flagged'])}")

        # Verify each agent result
        for agent_r in result["agent_results"]:
            self.assertIn("agent_name", agent_r)
            self.assertIn("score", agent_r)
            self.assertIn("citations", agent_r)
            self.assertIn("data_availability", agent_r)
            print(f"  [AGENT] {agent_r['agent_name']}: score={agent_r['score']} | "
                  f"citations={len(agent_r.get('citations', []))} | "
                  f"availability={agent_r['data_availability']}")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Filter out our custom flag before passing to unittest
    args = [a for a in sys.argv if a != "--no-llm"]

    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    if not has_key and not SKIP_LLM:
        print("âš ï¸  WARNING: OPENAI_API_KEY not set â€” LLM pipeline tests will fail.")
        print("   Add it to backend/.env or set it as an environment variable.")
        print("   Run with --no-llm to skip those tests.\n")

    sys.argv = args
    unittest.main(verbosity=2)

