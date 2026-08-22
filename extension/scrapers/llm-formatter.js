/**
 * llm-formatter.js — Dedicated LLM output formatter for Site Ranker
 *
 * Takes normalized listing data and produces a compact, structured payload
 * optimized for LLM consumption. Strips DOM noise, handles missing fields,
 * and remains deterministic.
 */

"use strict";

const SiteRankerLLMFormatter = {

  /**
   * Format normalized listing data for LLM consumption.
   * @param {object} normalized - { source, common, website_specific }
   * @returns {object} Compact LLM-ready payload
   */
  format(normalized) {
    const { source, common, website_specific } = normalized;
    const siteName = source?.website || "unknown";

    const result = {
      property: this._buildPropertySection(common),
      source: this._buildSourceSection(source, common),
    };

    // Add financials if present
    const financials = this._buildFinancialsSection(common, website_specific, siteName);
    if (financials && Object.keys(financials).length > 0) {
      result.financials = financials;
    }

    // Add building details if present
    const building = this._buildBuildingSection(common, website_specific, siteName);
    if (building && Object.keys(building).length > 0) {
      result.building = building;
    }

    // Add site-specific extras that don't fit elsewhere
    const extras = this._buildExtrasSection(website_specific, siteName);
    if (extras && Object.keys(extras).length > 0) {
      result.website_specific = extras;
    }

    return result;
  },

  _buildPropertySection(common) {
    const section = {};
    this._addIfPresent(section, "address", common.address);
    this._addIfPresent(section, "city", common.city);
    this._addIfPresent(section, "state", common.state);
    this._addIfPresent(section, "zip_code", common.zip_code);
    this._addIfPresent(section, "property_type", common.property_type);
    this._addIfPresent(section, "status", common.status);
    this._addIfPresent(section, "description", common.description);
    return section;
  },

  _buildSourceSection(source, common) {
    return {
      website: source?.website || null,
      url: common.listing_url || source?.url || null,
      listing_id: common.listing_id || source?.listing_id || null,
    };
  },

  _buildFinancialsSection(common, websiteSpecific, siteName) {
    const section = {};
    const siteData = websiteSpecific?.[siteName] || {};

    // Price
    if (common.price_text) {
      section.price = common.price_text;
    } else if (common.price) {
      section.price = common.price;
    }

    // Crexi-specific
    if (siteData.cap_rate) section.cap_rate = siteData.cap_rate;
    if (siteData.noi) section.noi = siteData.noi;

    // LoopNet-specific
    if (siteData.rental_rate) section.rental_rate = siteData.rental_rate;

    return section;
  },

  _buildBuildingSection(common, websiteSpecific, siteName) {
    const section = {};
    const siteData = websiteSpecific?.[siteName] || {};

    // Common building fields
    if (siteData.building_size) section.size = siteData.building_size;
    if (siteData.year_built) section.year_built = siteData.year_built;
    if (siteData.building_class) section.class = siteData.building_class;
    if (siteData.building_height) section.height = siteData.building_height;
    if (siteData.typical_floor_size) section.typical_floor = siteData.typical_floor_size;
    if (siteData.ceiling_height) section.ceiling_height = siteData.ceiling_height;
    if (siteData.parking) section.parking = siteData.parking;
    if (siteData.lot_size) section.lot_size = siteData.lot_size;

    // Crexi-specific
    if (siteData["Square Footage"]) section.size = siteData["Square Footage"];
    if (siteData["Year Built"]) section.year_built = siteData["Year Built"];
    if (siteData["Occupancy"]) section.occupancy = siteData["Occupancy"];

    return section;
  },

  _buildExtrasSection(websiteSpecific, siteName) {
    const siteData = websiteSpecific?.[siteName] || {};
    const extras = {};

    // LoopNet-specific
    if (siteData.loopnet_rating) extras.rating = siteData.loopnet_rating;
    if (siteData.available_spaces) extras.spaces = siteData.available_spaces;
    if (siteData.broker) extras.broker = siteData.broker;

    // Crexi-specific
    if (siteData.highlights) extras.highlights = siteData.highlights;

    return extras;
  },

  _addIfPresent(obj, key, value) {
    if (value != null && value !== "") {
      obj[key] = value;
    }
  },
};

if (typeof window !== "undefined") {
  window.SiteRankerLLMFormatter = SiteRankerLLMFormatter;
}
