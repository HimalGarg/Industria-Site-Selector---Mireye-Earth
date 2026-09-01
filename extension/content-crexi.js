/**
 * content-crexi.js — Site Ranker Capture — Crexi Adapter (v2 → v3 Adapter)
 *
 * Targets Crexi listing detail pages (PDP) — https://www.crexi.com/properties/* etc.
 *
 * Extends BaseAdapter to provide:
 *   - Tiered extraction (data-cy → semantic HTML → text patterns → utility classes)
 *   - Raw data preservation
 *   - Normalization into common + crexi-specific fields
 *   - LLM formatting via shared formatter
 *
 * All original v2 extraction logic is preserved and wrapped in the adapter pattern.
 * MutationObserver and SPA navigation handling are inherited from BaseAdapter.
 */

"use strict";

/* global SiteRankerBaseAdapter, SiteRankerNormalize, SiteRankerLLMFormatter */

class CrexiAdapter extends SiteRankerBaseAdapter {

  get siteName() { return "crexi"; }

  get hostnames() { return ["www.crexi.com", "crexi.com"]; }

  // ── Page Detection ─────────────────────────────────────────────────────────

  isListingPage() {
    const path = window.location.pathname;
    return (
      /\/properties\/\d+/.test(path) ||
      /\/lease\/properties\/\d+/.test(path) ||
      /\/industrial\/\d+/.test(path) ||
      /\/land\/\d+/.test(path) ||
      /\/multifamily\/\d+/.test(path) ||
      /\/office\/\d+/.test(path) ||
      /\/retail\/\d+/.test(path)
    );
  }

  getAnchorElement() {
    return document.querySelector('header[data-cy="pdpHeader"]');
  }

  // ── Raw Extraction (v2 confirmed selectors, preserved as-is) ───────────────

  extractRaw() {
    this.log("Extracting raw data...");
    const raw = {
      address: this._extractAddress(),
      listing_title: this._extractTitle(),
      price: this._extractPrice(),
      image_url: this._extractImage(),
      building_details: this._extractBuildingDetails(),
      description: this._extractDescription(),
      highlights: this._extractHighlights(),
      source_url: this._extractSourceUrl(),
      listing_id: this._extractListingId(),
      page_metadata: {
        og_title: SiteRankerNormalize.meta("og:title"),
        og_image: SiteRankerNormalize.meta("og:image"),
        og_description: SiteRankerNormalize.meta("og:description"),
        canonical: SiteRankerNormalize.attrFrom('link[rel="canonical"]', "href"),
      },
    };

    // Log field status
    for (const [key, val] of Object.entries(raw)) {
      if (key === "page_metadata" || key === "building_details") continue;
      this.logField(key, val ? "FOUND" : "NOT_FOUND");
    }

    return raw;
  }

  /**
   * Extract property address.
   * Confirmed selector: header[data-cy="pdpHeader"] h1
   */
  _extractAddress() {
    // Tier 1: confirmed data-cy selector
    const h1 = document.querySelector('header[data-cy="pdpHeader"] h1');
    if (h1) {
      const firstNode = h1.childNodes[0];
      if (firstNode && firstNode.nodeType === Node.TEXT_NODE) {
        const addr = firstNode.textContent.trim();
        if (addr) return addr;
      }
      const spanText = h1.querySelector("span")?.textContent?.trim() || "";
      const full = h1.textContent.trim();
      const stripped = full.replace(spanText, "").trim();
      if (stripped) return stripped;
    }

    // Tier 2: header h1
    const headerH1 = document.querySelector("header h1");
    if (headerH1) {
      const text = headerH1.childNodes[0]?.textContent?.trim() || headerH1.textContent.trim();
      if (text) return text;
    }

    // Tier 3: meta description pattern
    const metaDesc = document.querySelector('meta[name="description"]')?.content || "";
    const metaMatch = metaDesc.match(/(?:for (?:lease|sale) at )(.+?)(?:\.|$)/i);
    if (metaMatch?.[1]) {
      this.warn("Using tier-3 address fallback (meta description)");
      return metaMatch[1].trim();
    }

    // Tier 3b: street address text scan
    const allText = document.body.innerText;
    const addrMatch = allText.match(/\d+\s+[\w\s]+,\s+[\w\s]+,\s+[A-Z]{2}\s+\d{5}/);
    if (addrMatch) {
      this.warn("Using tier-3 address fallback (text scan)");
      return addrMatch[0].trim();
    }

    return null;
  }

  /**
   * Extract listing title (building name / headline).
   */
  _extractTitle() {
    // Tier 1a: rich title from about-property section
    const aboutTitle = document.querySelector("crx-smart-about-property h2");
    if (aboutTitle?.textContent?.trim()) return aboutTitle.textContent.trim();

    // Tier 1b: building name near price
    const priceH2 = document.querySelector(
      'h2.ctw\\:text-body.ctw\\:m-0.ctw\\:line-clamp-1'
    );
    if (priceH2?.textContent?.trim()) return priceH2.textContent.trim();

    // Tier 2: header area h2
    const header = document.querySelector('header[data-cy="pdpHeader"]');
    if (header) {
      const h2 = header.nextElementSibling?.querySelector("h2") || document.querySelector("main h2");
      if (h2?.textContent?.trim()) return h2.textContent.trim();
    }

    // Tier 3: og:title meta
    const ogTitle = document.querySelector('meta[property="og:title"]')?.content;
    if (ogTitle) return ogTitle.trim();

    return null;
  }

  /**
   * Extract price display string (v2: stored as raw string for sale or lease).
   */
  _extractPrice() {
    const primaryPrice = document.querySelector('[data-cy="primary-price"]');
    if (primaryPrice?.textContent?.trim()) return primaryPrice.textContent.trim();

    const auctionVal = document.querySelector('[data-cy="auctionDetailsValue"]');
    if (auctionVal?.textContent?.trim()) return auctionVal.textContent.trim();

    const allEls = document.querySelectorAll("span, div, p");
    for (const el of allEls) {
      const t = el.textContent.trim();
      if (/^\$[\d,]+/.test(t) && t.length < 35) {
        return t;
      }
    }

    return null;
  }

  /**
   * Extract image URL (v2 addition: primary listing photo).
   */
  _extractImage() {
    const img = document.querySelector('img[data-cy="image"]');
    if (img?.src) return img.src;

    const ogImg = document.querySelector('meta[property="og:image"]')?.content;
    if (ogImg) return ogImg;

    return null;
  }

  /**
   * Extract detailed property/investment summary pairs.
   */
  _extractBuildingDetails() {
    const labels = document.querySelectorAll('[data-cy="property-detail-summary"] [data-cy="label"]');
    const values = document.querySelectorAll('[data-cy="property-detail-summary"] [data-cy="value"]');

    if (labels.length === 0 || labels.length !== values.length) return null;

    const details = {};
    for (let i = 0; i < labels.length; i++) {
      const key = labels[i].textContent.trim();
      const val = values[i].textContent.trim();
      if (key && val) details[key] = val;
    }
    return Object.keys(details).length > 0 ? details : null;
  }

  /**
   * Extract marketing description.
   */
  _extractDescription() {
    const container = document.querySelector("crx-smart-about-property");
    if (!container) return null;

    const descBlock = container.querySelector("crx-safe-html-with-abs-links");
    if (descBlock?.textContent?.trim()) {
      return descBlock.textContent.trim();
    }

    const cyDesc = container.querySelector('[data-cy="description"], [data-cy="about-property-description"]');
    if (cyDesc?.textContent?.trim()) return cyDesc.textContent.trim();

    return null;
  }

  /**
   * Extract investment / building highlights.
   */
  _extractHighlights() {
    const container = document.querySelector("crx-smart-about-property");
    if (!container) return null;

    const blocks = container.querySelectorAll("crx-safe-html-with-abs-links");
    if (blocks.length > 1 && blocks[1]?.textContent?.trim()) {
      return blocks[1].textContent.trim();
    }

    const lis = container.querySelectorAll("li");
    if (lis.length > 0) {
      const items = [...lis].map(li => li.textContent.trim()).filter(Boolean);
      if (items.length) return items.join(" | ");
    }

    return null;
  }

  /**
   * Extract clean canonical URL.
   */
  _extractSourceUrl() {
    return (
      document.querySelector('link[rel="canonical"]')?.href ||
      window.location.href
    );
  }

  /**
   * Extract listing ID from URL.
   */
  _extractListingId() {
    const match = window.location.pathname.match(/\/(\d+)(?:\/|$)/);
    return match ? match[1] : null;
  }

  // ── Normalization ──────────────────────────────────────────────────────────

  normalize(raw) {
    const N = SiteRankerNormalize;
    const parsedPrice = N.parsePrice(raw.price);
    const parsedAddress = N.parseAddress(raw.address);

    return {
      source: {
        website: this.siteName,
        url: raw.source_url || window.location.href,
        listing_id: raw.listing_id,
        scraped_at: new Date().toISOString(),
      },
      common: {
        title: N.clean(raw.listing_title),
        address: N.clean(raw.address),
        city: parsedAddress.city,
        state: parsedAddress.state,
        zip_code: parsedAddress.zip,
        property_type: raw.building_details?.["Property Type"] || raw.building_details?.["Property Subtype"] || null,
        price: parsedPrice.value,
        price_text: parsedPrice.raw || null,
        status: null,  // Crexi doesn't expose status in a consistent way
        description: N.clean(raw.description),
        listing_url: raw.source_url,
        listing_id: raw.listing_id,
        images: raw.image_url ? [raw.image_url] : [],
      },
      website_specific: {
        crexi: {
          ...raw.building_details || {},
          highlights: raw.highlights || null,
          image_url: raw.image_url,
        },
      },
    };
  }

  // ── LLM Formatting ─────────────────────────────────────────────────────────

  formatForLLM(normalized) {
    return SiteRankerLLMFormatter.format(normalized);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────

const crexiAdapter = new CrexiAdapter();

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => crexiAdapter.boot());
} else {
  crexiAdapter.boot();
}

