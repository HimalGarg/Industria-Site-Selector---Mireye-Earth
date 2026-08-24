/**
 * normalize.js — Shared normalization utilities for Site Ranker
 *
 * Pure functions for parsing and normalizing field values across all sites.
 * No DOM access — operates only on strings/numbers.
 */

"use strict";

const SiteRankerNormalize = {

  /**
   * Parse a price string into a numeric value (cents-free).
   * Handles: "$2,500,000", "$2.5M", "$500/SF", "Upon Request", etc.
   * @param {string} raw
   * @returns {{ value: number|null, raw: string, unit: string|null }}
   */
  parsePrice(raw) {
    if (!raw || typeof raw !== "string") return { value: null, raw: raw || "", unit: null };

    const cleaned = raw.trim();

    // "Upon Request", "Contact for pricing", "N/A" etc.
    if (/upon request|contact|n\/a|call/i.test(cleaned)) {
      return { value: null, raw: cleaned, unit: null };
    }

    // Detect unit suffix: /SF/YR, /SF/MO, /MO, /YR
    let unit = null;
    const unitMatch = cleaned.match(/\/(SF|MO|YR|AC|Unit)/gi);
    if (unitMatch) {
      unit = unitMatch.map(u => u.replace("/", "")).join("/");
    }

    // Try "$2.5M" / "$1.2B" style
    const shortMatch = cleaned.match(/\$\s*([\d,.]+)\s*(M|B|K)/i);
    if (shortMatch) {
      const num = parseFloat(shortMatch[1].replace(/,/g, ""));
      const multiplier = { K: 1_000, M: 1_000_000, B: 1_000_000_000 }[shortMatch[2].toUpperCase()] || 1;
      return { value: Math.round(num * multiplier), raw: cleaned, unit };
    }

    // Try standard "$2,500,000" style
    const stdMatch = cleaned.match(/\$\s*([\d,]+(?:\.\d+)?)/);
    if (stdMatch) {
      const num = parseFloat(stdMatch[1].replace(/,/g, ""));
      return { value: isNaN(num) ? null : Math.round(num), raw: cleaned, unit };
    }

    // Just a number
    const numOnly = cleaned.replace(/[^0-9.]/g, "");
    if (numOnly) {
      const num = parseFloat(numOnly);
      return { value: isNaN(num) ? null : Math.round(num), raw: cleaned, unit };
    }

    return { value: null, raw: cleaned, unit };
  },

  /**
   * Parse a square footage string.
   * Handles: "5,000 SF", "5000 sq ft", "5,000 - 10,000 SF"
   * @param {string} raw
   * @returns {{ value: number|null, raw: string }}
   */
  parseSqFt(raw) {
    if (!raw || typeof raw !== "string") return { value: null, raw: raw || "" };
    const cleaned = raw.trim();

    // Range: take the first number
    const rangeMatch = cleaned.match(/([\d,]+)\s*[-–]\s*([\d,]+)/);
    if (rangeMatch) {
      const low = parseInt(rangeMatch[1].replace(/,/g, ""), 10);
      const high = parseInt(rangeMatch[2].replace(/,/g, ""), 10);
      return { value: low, high, raw: cleaned };
    }

    const numMatch = cleaned.match(/([\d,]+)/);
    if (numMatch) {
      const num = parseInt(numMatch[1].replace(/,/g, ""), 10);
      return { value: isNaN(num) ? null : num, raw: cleaned };
    }

    return { value: null, raw: cleaned };
  },

  /**
   * Parse an address string into components.
   * Best-effort — not a full geocoder.
   * @param {string} raw
   * @returns {{ street: string|null, city: string|null, state: string|null, zip: string|null, full: string }}
   */
  parseAddress(raw) {
    if (!raw || typeof raw !== "string") return { street: null, city: null, state: null, zip: null, full: raw || "" };
    const cleaned = raw.trim();

    // Pattern: "667 Madison Ave, New York, NY 10065"
    const fullMatch = cleaned.match(/^(.+?),\s*(.+?),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?/);
    if (fullMatch) {
      return {
        street: fullMatch[1].trim(),
        city: fullMatch[2].trim(),
        state: fullMatch[3].trim(),
        zip: fullMatch[4]?.trim() || null,
        full: cleaned,
      };
    }

    // Pattern: "667 Madison Ave, New York NY 10065" (no comma before state)
    const altMatch = cleaned.match(/^(.+?),\s*(.+?)\s+([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?/);
    if (altMatch) {
      return {
        street: altMatch[1].trim(),
        city: altMatch[2].trim(),
        state: altMatch[3].trim(),
        zip: altMatch[4]?.trim() || null,
        full: cleaned,
      };
    }

    return { street: cleaned, city: null, state: null, zip: null, full: cleaned };
  },

  /**
   * Clean a string — trim, collapse whitespace, remove nbsp.
   * @param {string|null} val
   * @returns {string|null}
   */
  clean(val) {
    if (val == null) return null;
    const cleaned = String(val)
      .replace(/\u00A0/g, " ")   // nbsp
      .replace(/\s+/g, " ")
      .trim();
    return cleaned || null;
  },

  /**
   * Safely extract text content from a selector.
   * @param {string} selector
   * @param {Element} [root=document]
   * @returns {string|null}
   */
  textFrom(selector, root = document) {
    const el = root.querySelector(selector);
    return el ? this.clean(el.textContent) : null;
  },

  /**
   * Safely extract an attribute value from a selector.
   * @param {string} selector
   * @param {string} attr
   * @param {Element} [root=document]
   * @returns {string|null}
   */
  attrFrom(selector, attr, root = document) {
    const el = root.querySelector(selector);
    return el ? (el.getAttribute(attr) || null) : null;
  },

  /**
   * Extract meta tag content by property or name.
   * @param {string} key - e.g. "og:title" or "description"
   * @returns {string|null}
   */
  meta(key) {
    // Try property first (og:*, twitter:*)
    const byProp = document.querySelector(`meta[property="${key}"]`);
    if (byProp?.content) return this.clean(byProp.content);

    // Then name
    const byName = document.querySelector(`meta[name="${key}"]`);
    if (byName?.content) return this.clean(byName.content);

    return null;
  },
};

if (typeof window !== "undefined") {
  window.SiteRankerNormalize = SiteRankerNormalize;
}
