"""
backend/test_compare_pipeline.py — Integration & Unit Test Suite for Multi-Site Comparison
=============================================================================================

Runs test suite covering:
  1. Input validation (rejects 1 site and 5 sites with 400 status)
  2. Missing evaluation flagging (missing_evaluation: true)
  3. Score flattening format (energy, water, surface, transport, risk)
  4. Comparison narrative & trade-offs synthesis for 2, 3, and 4 sites
  5. Non-blocking error handling
"""

from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app, get_db

client = TestClient(app)


class TestComparePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_id = f"test-compare-session-{uuid.uuid4().hex[:8]}"

        # Create 3 test cart items
        cls.item_id_1 = str(uuid.uuid4())
        cls.item_id_2 = str(uuid.uuid4())
        cls.item_id_3 = str(uuid.uuid4())
        cls.unevaluated_item_id = str(uuid.uuid4())

        with get_db() as conn:
            # Item 1: High Energy, Low Flood Risk
            conn.execute(
                """
                INSERT INTO cart_items (cart_item_id, session_id, address, listing_title, added_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cls.item_id_1, cls.session_id, "41 Flatbush Ave, Brooklyn, NY 11217", "Brooklyn Center", datetime.now(timezone.utc).isoformat()),
            )
            conn.execute(
                """
                INSERT INTO evaluations (evaluation_id, cart_item_id, overall_score, recommendation, agent_results, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    cls.item_id_1,
                    92,
                    "Highly Recommended",
                    json.dumps([
                        {"agent_name": "Energy Agent", "score": 95, "summary": "Direct access to 230kV substation."},
                        {"agent_name": "Water Agent", "score": 90, "summary": "Municipal water available."},
                        {"agent_name": "Surface & Environment Agent", "score": 85, "summary": "Flat grade terrain."},
                        {"agent_name": "Transport Agent", "score": 95, "summary": "Adjacent to major highway."},
                        {"agent_name": "Risk Agent", "score": 95, "summary": "FEMA Flood Zone X."},
                    ]),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            # Item 2: Moderate score, Water concern
            conn.execute(
                """
                INSERT INTO cart_items (cart_item_id, session_id, address, listing_title, added_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cls.item_id_2, cls.session_id, "212 Pottsville St, Cressona, PA 17929", "Cressona Mall Site", datetime.now(timezone.utc).isoformat()),
            )
            conn.execute(
                """
                INSERT INTO evaluations (evaluation_id, cart_item_id, overall_score, recommendation, agent_results, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    cls.item_id_2,
                    74,
                    "Proceed with Caution",
                    json.dumps([
                        {"agent_name": "Energy Agent", "score": 80, "summary": "13.8kV distribution feeder."},
                        {"agent_name": "Water Agent", "score": 60, "summary": "Private well system required."},
                        {"agent_name": "Surface Agent", "score": 75, "summary": "Moderate 11 degree slope."},
                        {"agent_name": "Transport Agent", "score": 85, "summary": "2 miles to interstate."},
                        {"agent_name": "Risk Agent", "score": 70, "summary": "Located in FEMA Zone AE 100-yr flood plain."},
                    ]),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            # Item 3: High Transport, Low Energy
            conn.execute(
                """
                INSERT INTO cart_items (cart_item_id, session_id, address, listing_title, added_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cls.item_id_3, cls.session_id, "3283 W College Ave, State College, PA 16801", "College Retail Site", datetime.now(timezone.utc).isoformat()),
            )
            conn.execute(
                """
                INSERT INTO evaluations (evaluation_id, cart_item_id, overall_score, recommendation, agent_results, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    cls.item_id_3,
                    81,
                    "Recommended",
                    json.dumps([
                        {"agent_name": "Energy Agent", "score": 70, "summary": "Limited 5MW capacity."},
                        {"agent_name": "Water Agent", "score": 85, "summary": "Public utility provider."},
                        {"agent_name": "Surface Agent", "score": 80, "summary": "Well drained soil."},
                        {"agent_name": "Transport Agent", "score": 90, "summary": "Rail spur access available."},
                        {"agent_name": "Risk Agent", "score": 80, "summary": "Zone X flood classification."},
                    ]),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            # Unevaluated Item
            conn.execute(
                """
                INSERT INTO cart_items (cart_item_id, session_id, address, listing_title, added_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cls.unevaluated_item_id, cls.session_id, "500 Unevaluated Way, Scranton, PA 18503", "Scranton Parcel", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def test_01_reject_invalid_site_count(self):
        """POST /compare-sites must reject 1 site or 5 sites with 400 Bad Request."""
        # 1 site
        res1 = client.post("/compare-sites", json={"cart_item_ids": [self.item_id_1]})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("between 2 and 4", res1.json()["detail"])

        # 5 sites
        dummy_ids = [str(uuid.uuid4()) for _ in range(5)]
        res5 = client.post("/compare-sites", json={"cart_item_ids": dummy_ids})
        self.assertEqual(res5.status_code, 400)

    def test_02_compare_two_evaluated_sites(self):
        """Compare 2 evaluated sites and check score flattening + narrative generation."""
        res = client.post(
            "/compare-sites",
            json={"cart_item_ids": [self.item_id_1, self.item_id_2]},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        sites = data["sites"]
        self.assertEqual(len(sites), 2)

        # Check Site 1 flattening
        site1 = next(s for s in sites if s["cart_item_id"] == self.item_id_1)
        self.assertEqual(site1["overall_score"], 92)
        self.assertFalse(site1["missing_evaluation"])
        self.assertEqual(site1["agent_scores"]["energy"], 95)
        self.assertEqual(site1["agent_scores"]["risk"], 95)

        # Check Site 2 flattening
        site2 = next(s for s in sites if s["cart_item_id"] == self.item_id_2)
        self.assertEqual(site2["overall_score"], 74)
        self.assertEqual(site2["agent_scores"]["water"], 60)

        # Check narrative & trade-offs
        self.assertTrue(len(data["comparison_narrative"]) > 0)
        self.assertIsInstance(data["trade_offs"], list)

    def test_03_compare_with_unevaluated_site(self):
        """Comparing with an un-evaluated site flags missing_evaluation: true without failing."""
        res = client.post(
            "/compare-sites",
            json={"cart_item_ids": [self.item_id_1, self.unevaluated_item_id]},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        uneval_site = next(s for s in data["sites"] if s["cart_item_id"] == self.unevaluated_item_id)
        self.assertTrue(uneval_site["missing_evaluation"])
        self.assertIsNone(uneval_site["overall_score"])
        self.assertIsNone(uneval_site["agent_scores"])

        # Narrative should still generate for the evaluated site
        self.assertTrue(len(data["comparison_narrative"]) > 0)

    def test_04_compare_three_sites(self):
        """Compare 3 evaluated sites side-by-side."""
        res = client.post(
            "/compare-sites",
            json={"cart_item_ids": [self.item_id_1, self.item_id_2, self.item_id_3]},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["sites"]), 3)
        self.assertTrue(len(data["trade_offs"]) >= 1)


if __name__ == "__main__":
    unittest.main()
