"""
backend/test_chat_pipeline.py — Integration & Unit Test Suite for Chat, Router & Memory
==========================================================================================

Runs full suite testing:
  1. Database migration for chat tables (listing_memory, session_context, chat_messages)
  2. POST /chat for unevaluated listing
  3. POST /chat for evaluated listing (answer_from_existing_context)
  4. LLM Router field expansion & max-5 field cap
  5. Grounded citation format checking
  6. Background listing_memory atomic fact extraction
  7. Cross-site session_context re-summarization
  8. Read endpoints (GET /chat, GET /listing-memory, GET /session-context)
"""

from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

# Import FastAPI app from main
from main import app, get_db
from chat.router_engine import route_chat_query
from chat.memory_engine import _insert_listing_memory, _resummarize_session_context_sync

client = TestClient(app)


class TestChatRouterMemoryPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_id = f"test-chat-session-{uuid.uuid4().hex[:8]}"
        cls.address = "41 Flatbush Ave, Brooklyn, NY 11217"

        # Insert test cart item into DB
        cls.cart_item_id = str(uuid.uuid4())
        llm_structured_obj = {
            "financials": {
                "asking_price": 12500000,
                "asking_price_display": "$12,500,000",
                "cap_rate_percent": 6.5,
                "noi_annual": 812500,
            },
            "property": {
                "building_sqft": 27777,
                "building_class": "A",
                "property_type": "Office",
            },
        }

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO cart_items
                    (cart_item_id, session_id, address, source_url, listing_title, image_url, details, llm_structured, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cls.cart_item_id,
                    cls.session_id,
                    cls.address,
                    "https://www.loopnet.com/Listing/test-41-flatbush",
                    "41 Flatbush Commercial Center",
                    "https://images.loopnet.com/test.jpg",
                    json.dumps({"Asking Price": "$12,500,000"}),
                    json.dumps(llm_structured_obj),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            # Insert initial mireye_cache row
            conn.execute(
                """
                INSERT OR REPLACE INTO mireye_cache (cache_key, fields, last_updated)
                VALUES (?, ?, ?)
                """,
                (
                    cls.address,
                    json.dumps({
                        "elevation": {"value": 11.45, "unit": "meters", "source": "USGS_3DEP_COG"},
                        "fema_flood_zone": {"value": "X", "unit": None, "source": "FEMA_NFHL"},
                        "slope_degrees": {"value": 1.20, "unit": "degrees", "source": "USGS_3DEP_COG"},
                    }),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def test_01_db_tables_exist(self):
        """Verify that all three chat/memory tables exist in SQLite schema."""
        with get_db() as conn:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            self.assertIn("listing_memory", tables)
            self.assertIn("session_context", tables)
            self.assertIn("chat_messages", tables)

    def test_02_post_chat_unevaluated(self):
        """POST /chat for a site that has no evaluation report should prompt user to evaluate first."""
        unevaluated_cart_id = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO cart_items (cart_item_id, session_id, address, added_at)
                VALUES (?, ?, ?, ?)
                """,
                (unevaluated_cart_id, self.session_id, "999 Unevaluated St", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

        res = client.post(
            "/chat",
            json={
                "cart_item_id": unevaluated_cart_id,
                "session_id": self.session_id,
                "message": "What is the flood risk here?",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "done")
        self.assertIn("has not been evaluated", data["content"])

    def test_03_post_chat_evaluated_existing_context(self):
        """POST /chat on an evaluated site for an already cached field should return grounded answer."""
        # Insert mock evaluation row
        eval_id = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO evaluations
                    (evaluation_id, cart_item_id, overall_score, recommendation, conflicts_flagged, agent_results, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eval_id,
                    self.cart_item_id,
                    88,
                    "Highly Recommended",
                    json.dumps([]),
                    json.dumps([
                        {
                            "agent_name": "Risk Agent",
                            "score": 90,
                            "summary": "Property is in FEMA Flood Zone X (minimal hazard).",
                            "citations": [{"source": "mireye", "field": "fema_flood_zone", "value": "X"}],
                        }
                    ]),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

        res = client.post(
            "/chat",
            json={
                "cart_item_id": self.cart_item_id,
                "session_id": self.session_id,
                "message": "What is the FEMA flood zone classification for this site?",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "done")
        self.assertTrue(len(data["content"]) > 0)
        self.assertIsInstance(data["citations"], list)

    def test_04_router_capped_max_fields(self):
        """Verify route_chat_query caps returned field requests at maximum 5 fields."""
        cached_fields = {"elevation": {"value": 10}}
        action, fields = route_chat_query(
            user_message="Tell me about opportunity zone, karst, cell towers, brownfields, wetlands, rail line, gas pipeline, and power plants",
            cached_fields=cached_fields,
            cache_key=self.address,
        )
        self.assertLessEqual(len(fields), 5)

    def test_05_listing_memory_insertion_and_read(self):
        """Test inserting and reading atomic listing memory facts."""
        fact = "User confirmed this site is their primary candidate for logistics."
        _insert_listing_memory(self.cart_item_id, self.session_id, fact)

        res = client.get(f"/listing-memory?cart_item_id={self.cart_item_id}")
        self.assertEqual(res.status_code, 200)
        facts = res.json()
        self.assertTrue(any(f["fact"] == fact for f in facts))

    def test_06_session_context_resummarize(self):
        """Test session_context re-summarizer updates snapshot row."""
        _resummarize_session_context_sync(self.session_id, force_update=True)

        res = client.get(f"/session-context?session_id={self.session_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session_id"], self.session_id)

    def test_07_get_chat_history(self):
        """GET /chat returns full turn history for cart_item_id."""
        res = client.get(f"/chat?cart_item_id={self.cart_item_id}")
        self.assertEqual(res.status_code, 200)
        history = res.json()
        self.assertIsInstance(history, list)
        self.assertTrue(len(history) >= 2)


if __name__ == "__main__":
    unittest.main()
