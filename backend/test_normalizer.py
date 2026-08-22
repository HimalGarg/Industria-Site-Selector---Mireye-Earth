"""
backend/test_normalizer.py — Unit Tests for LLM Normalization Engine

Per Step 18 of llm_structured_normalization_guide.md:
  1. Test 1: Sale listing normalization
  2. Test 2: Lease rate handling
  3. Test 3: Missing sale fields
  4. Test 4: Boolean and Date normalization
  5. Test 5: No raw duplication inside llm_structured
  6. Test 6: Raw preservation (provenance / non-mutation)
  7. Test 7: Step 19 Wendy's canonical validation
"""

import unittest
from main import (
    build_llm_structured_data,
    parse_boolean,
    parse_date_iso,
    parse_price_numeric,
)


class TestLLMNormalizer(unittest.TestCase):

    def test_1_sale_listing(self):
        """Test 1: Sale listing numeric parsing, cap rate, NOI, sqft, year built."""
        details = {
            "price": "$2,037,286",
            "Cap Rate": "7.00%",
            "NOI": "$142,610",
            "Square Footage": "2,629",
            "Year Built": "1976",
        }
        res = build_llm_structured_data(
            address="100 N Progress Ave",
            listing_title="Wendy's",
            source_url="https://crexi.com/p/123",
            image_url="https://crexi.com/img.jpg",
            details=details,
        )

        self.assertEqual(res["financials"]["asking_price"], 2037286)
        self.assertEqual(res["financials"]["asking_price_display"], "$2,037,286")
        self.assertEqual(res["financials"]["cap_rate_percent"], 7.0)
        self.assertEqual(res["financials"]["noi_annual"], 142610)
        self.assertEqual(res["property"]["building_sqft"], 2629)
        self.assertEqual(res["property"]["year_built"], 1976)

    def test_2_lease_rate_handling(self):
        """Test 2: Lease rate strings such as $16/SF/YR are preserved in display but asking_price is None."""
        details = {
            "price": "$16/SF/YR",
        }
        res = build_llm_structured_data(
            address="123 Main St",
            listing_title="Lease Space",
            source_url="https://crexi.com/p/456",
            image_url=None,
            details=details,
        )

        self.assertEqual(res["financials"]["asking_price_display"], "$16/SF/YR")
        self.assertIsNone(res["financials"]["asking_price"])

    def test_3_missing_sale_fields(self):
        """Test 3: Missing Cap Rate / NOI does not break normalization; returns null."""
        details = {
            "price": "$500,000",
        }
        res = build_llm_structured_data(
            address="Land Parcel 5",
            listing_title="Land Site",
            source_url=None,
            image_url=None,
            details=details,
        )

        self.assertIsNone(res["financials"]["cap_rate_percent"])
        self.assertIsNone(res["financials"]["noi_annual"])
        self.assertEqual(res["financials"]["asking_price"], 500000)

    def test_4_boolean_and_date_normalization(self):
        """Test 4: Rent Bumps/Ground Lease booleans and ISO date conversion (MM/DD/YYYY -> YYYY-MM-DD)."""
        # Test Date helper
        self.assertEqual(parse_date_iso("04/19/2017"), "2017-04-19")
        self.assertEqual(parse_date_iso("04/30/2037"), "2037-04-30")

        # Test Boolean helper
        self.assertEqual(parse_boolean("Yes"), True)
        self.assertEqual(parse_boolean("No"), False)

        details = {
            "Ground Lease": "No",
            "Broker Co-Op": "Yes",
            "Rent Bumps": "Yes",
            "Lease Commencement": "04/19/2017",
            "Lease Expiration": "04/30/2037",
        }
        res = build_llm_structured_data(
            address="Test Site",
            listing_title="Test",
            source_url=None,
            image_url=None,
            details=details,
        )

        self.assertEqual(res["investment"]["ground_lease"], False)
        self.assertEqual(res["investment"]["broker_co_op"], True)
        self.assertEqual(res["lease"]["rent_bumps"], True)
        self.assertEqual(res["lease"]["lease_commencement"], "2017-04-19")
        self.assertEqual(res["lease"]["lease_expiration"], "2037-04-30")

    def test_4b_schedule_rent_bumps_preservation(self):
        """Test 4b: Complex rent bumps schedule string is preserved as text, not boolean."""
        details = {
            "Rent Bumps": "10% every 5 years",
        }
        res = build_llm_structured_data(
            address="Test Site",
            listing_title="Test",
            source_url=None,
            image_url=None,
            details=details,
        )
        self.assertEqual(res["lease"]["rent_bumps"], "10% every 5 years")

    def test_5_no_raw_duplication(self):
        """Test 5: Assert llm_structured.raw_attributes does not exist."""
        details = {"Key": "Value"}
        res = build_llm_structured_data(
            address="Address",
            listing_title="Title",
            source_url=None,
            image_url=None,
            details=details,
        )
        self.assertNotIn("raw_attributes", res)

    def test_6_raw_preservation(self):
        """Test 6: Verify normalization does not mutate the original raw details dict."""
        raw_input = {
            "Square Footage": "2,629",
            "Cap Rate": "7.00%",
        }
        raw_input_copy = dict(raw_input)

        build_llm_structured_data(
            address="Address",
            listing_title="Title",
            source_url=None,
            image_url=None,
            details=raw_input,
        )

        # Assert raw dict is completely unchanged
        self.assertEqual(raw_input, raw_input_copy)

    def test_7_step_19_wendys_example_validation(self):
        """Test 7: Step 19 canonical validation against real Wendy's example from guide."""
        raw = {
            "Property Type": "Retail",
            "Sub Type": "Restaurant, QSR/Fast Food",
            "Square Footage": "2,629",
            "Cap Rate": "7.00%",
            "NOI": "$142,610",
            "Tenancy": "Single",
            "Brand/Tenant": "Wendy's",
            "Lease Type": "NNN",
            "Lease Term": "20",
            "Lease Expiration": "04/30/2037",
            "Year Built": "1976",
            "Acreage": "0.900",
            "Investment Type": "Net Lease",
            "Tenant Credit": "Franchisee",
            "Lease Commencement": "04/19/2017",
            "Ground Lease": "No",
            "Ownership": "Fee Simple",
            "price": "$2,037,286  |  56 days on market  |  Updated 20 days ago",
            "description": "Surmount is pleased to present the exclusive listing for a Wendy's...",
            "highlights": "Strong Franchisee Guarantee | Surrounding Demographics",
        }

        res = build_llm_structured_data(
            address="100 North Progress Avenue, Harrisburg, PA 17109",
            listing_title="Retail | 7.00% CAP | 2,629 SqFt",
            source_url="https://www.crexi.com/properties/2601532/pennsylvania-wendys",
            image_url=None,
            details=raw,
        )

        self.assertEqual(res["schema_version"], "1.0")
        self.assertEqual(res["identity"]["address"], "100 North Progress Avenue, Harrisburg, PA 17109")
        self.assertEqual(res["financials"]["asking_price_display"], "$2,037,286")
        self.assertEqual(res["financials"]["asking_price"], 2037286)
        self.assertEqual(res["financials"]["cap_rate_percent"], 7.0)
        self.assertEqual(res["financials"]["noi_annual"], 142610)
        self.assertEqual(res["property"]["building_sqft"], 2629)
        self.assertEqual(res["property"]["lot_acres"], 0.9)
        self.assertEqual(res["property"]["year_built"], 1976)
        self.assertEqual(res["lease"]["tenant"], "Wendy's")
        self.assertEqual(res["lease"]["tenancy"], "Single")
        self.assertEqual(res["lease"]["lease_type"], "NNN")
        self.assertEqual(res["lease"]["lease_commencement"], "2017-04-19")
        self.assertEqual(res["lease"]["lease_expiration"], "2037-04-30")
        self.assertEqual(res["investment"]["investment_type"], "Net Lease")
        self.assertEqual(res["investment"]["ground_lease"], False)
        self.assertEqual(res["listing_freshness"]["days_on_market"], 56)
        self.assertEqual(res["listing_freshness"]["days_since_update"], 20)
        self.assertEqual(len(res["narrative"]["highlights"]), 2)


if __name__ == "__main__":
    unittest.main()
