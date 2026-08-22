/**
 * content-loopnet.js — Site Ranker Capture — LoopNet Adapter
 *
 * Targets LoopNet listing detail pages (LDP):
 *   https://www.loopnet.com/Listing/{slug}/{id}/
 *
 * Extends BaseAdapter to provide:
 *   - Multi-source extraction: meta tags → data attributes → DOM selectors → embedded JSON
 *   - Raw data preservation (all original LoopNet field names)
 *   - Normalization into common + loopnet-specific fields
 *   - LLM formatting via shared formatter
 *
 * LoopNet data sources (by reliability):
 *   ★★★ data-listing-id/type/state attributes on body/tracking element
 *   ★★★ og:title, og:image, og:description meta tags
 *   ★★★ .profile-hero__segment (street address)
 *   ★★★ .profile-hero-sub-title (availability summary w/ city/state/zip)
 *   ★★★ #property-facts .property-fact-value-container[data-fact-type]
 *   ★★★ data-fields JSON attribute (per-space details)
 *   ★★  breadcrumbs (.breadcrumbs__crumb-title)
 *   ★★  #contact-form-contacts (broker info)
 *   ★★★ img[src*="images1.loopnet.com"] (listing images)
 *
 * No JSON-LD or window.__ embedded state available on LoopNet.
 */

"use strict";

/* global SiteRankerBaseAdapter, SiteRankerNormalize, SiteRankerLLMFormatter */

class LoopNetAdapter extends SiteRankerBaseAdapter {

  get siteName() { return "loopnet"; }

  get hostnames() { return ["www.loopnet.com", "loopnet.com"]; }

  // ── Page Detection ─────────────────────────────────────────────────────────

  isListingPage() {
    const path = window.location.pathname;
    // LoopNet listing URLs: /Listing/{slug}/{id}/
    return /\/Listing\/[^/]+\/\d+\/?/.test(path);
  }

  getAnchorElement() {
    // Inject button near the profile hero heading
    return (
      document.querySelector(".profile-hero-heading") ||
      document.querySelector(".profile-hero-heading-wrap") ||
      document.querySelector("h1.profile-hero-title")?.parentElement ||
      null
    );
  }

  // ── Raw Extraction ─────────────────────────────────────────────────────────

  extractRaw() {
    this.log("Extracting raw data from LoopNet...");
    const N = SiteRankerNormalize;

    const raw = {
      // Source 1: Data attributes (most stable)
      listing_id: this._extractDataAttr("data-listing-id"),
      listing_type: this._extractDataAttr("data-listing-type"),
      listing_state: this._extractDataAttr("data-listing-state"),
      listing_country: this._extractDataAttr("data-listing-country"),

      // Source 2: Meta tags
      og_title: N.meta("og:title"),
      og_image: N.meta("og:image"),
      og_description: N.meta("og:description"),
      og_url: N.meta("og:url"),
      meta_description: N.meta("description"),
      meta_keywords: N.meta("keywords"),

      // Source 3: Canonical URL
      canonical_url: N.attrFrom('link[rel="canonical"]', "href"),

      // Source 4: Profile hero (address & summary)
      hero_address: this._extractHeroAddress(),
      hero_subtitle: this._extractHeroSubtitle(),

      // Source 5: Page title
      page_title: document.title || null,

      // Source 6: Property facts (structured key-value pairs)
      property_facts: this._extractPropertyFacts(),

      // Source 7: Available spaces (data-fields JSON)
      available_spaces: this._extractAvailableSpaces(),

      // Source 8: Breadcrumb address
      breadcrumb_address: this._extractBreadcrumbAddress(),

      // Source 9: Broker/contact info
      broker_info: this._extractBrokerInfo(),

      // Source 10: Images
      images: this._extractImages(),

      // Source 11: Brochure URL
      brochure_url: this._extractBrochureUrl(),

      // Source 12: Property timestamp
      property_timestamp: N.textFrom("#PropertyTimeStamp"),
    };

    // Log field status
    const fields = [
      "listing_id", "listing_type", "og_title", "og_image",
      "hero_address", "hero_subtitle", "property_facts",
      "available_spaces", "breadcrumb_address", "broker_info", "images",
    ];
    for (const key of fields) {
      const val = raw[key];
      const found = val != null && (typeof val !== "object" || (Array.isArray(val) ? val.length > 0 : Object.keys(val).length > 0));
      this.logField(key, found ? "FOUND" : "NOT_FOUND", this._getSourceType(key));
    }

    return raw;
  }

  // ── Individual Extractors ──────────────────────────────────────────────────

  /**
   * Extract a data-* attribute from the tracking/body element.
   * LoopNet puts listing metadata on a div near the bottom of the page.
   */
  _extractDataAttr(attrName) {
    // Check elements with the attribute
    const el = document.querySelector(`[${attrName}]`);
    return el ? el.getAttribute(attrName) : null;
  }

  /**
   * Extract street address from the profile hero section.
   * Selector: .profile-hero__segment (inside h1.profile-hero-title)
   */
  _extractHeroAddress() {
    // Primary: the __segment span contains the street address
    const segment = document.querySelector(".profile-hero__segment");
    if (segment?.textContent?.trim()) return segment.textContent.trim();

    // Fallback: h1.profile-hero-title main title span
    const mainTitle = document.querySelector(".profile-hero-main-title");
    if (mainTitle?.textContent?.trim()) return mainTitle.textContent.trim();

    // Fallback: h1 text
    const h1 = document.querySelector("h1.profile-hero-title");
    if (h1) {
      const firstText = h1.childNodes[0]?.textContent?.trim();
      if (firstText) return firstText;
    }

    return null;
  }

  /**
   * Extract the subtitle from profile hero.
   * Contains: SF range, rating, property type, city/state/zip.
   * Example: "6,300 - 48,175 SF of 4-Star Office  Space Available in New York, NY 10065"
   */
  _extractHeroSubtitle() {
    const sub = document.querySelector(".profile-hero-sub-title");
    if (sub?.textContent?.trim()) return sub.textContent.trim();
    return null;
  }

  /**
   * Extract structured property facts from the #property-facts section.
   * Each fact has a data-fact-type attribute: BuildingType, YearBuiltRenovated, etc.
   */
  _extractPropertyFacts() {
    const facts = {};
    const factContainers = document.querySelectorAll(".property-fact-value-container[data-fact-type]");

    for (const container of factContainers) {
      const factType = container.getAttribute("data-fact-type");
      const label = container.querySelector(".fact-name")?.textContent?.trim();
      const valueEl = container.querySelector(".property-facts__data-item-text");

      // Some facts have multiple values (e.g. Parking)
      const valueEls = container.querySelectorAll(".property-facts__data-item-text");
      let value;
      if (valueEls.length > 1) {
        value = [...valueEls].map(el => el.textContent.trim()).filter(Boolean);
      } else {
        value = valueEl?.textContent?.trim() || null;
      }

      if (factType && value) {
        facts[factType] = {
          label: label || factType,
          value,
          data_fact_type: factType,
        };
      }
    }

    // Also check the labels-item pattern (e.g. Parking has a different structure)
    const labelItems = document.querySelectorAll(".property-facts__labels-item[data-fact-type]");
    for (const item of labelItems) {
      const factType = item.getAttribute("data-fact-type");
      if (facts[factType]) continue; // Already captured

      const label = item.textContent?.trim();
      // Find the sibling data item
      const dataItem = item.parentElement?.querySelector(`.property-facts__data-item[data-fact-type="${factType}"]`);
      if (dataItem) {
        const valueEls = dataItem.querySelectorAll(".property-facts__data-item-text");
        const value = valueEls.length > 1
          ? [...valueEls].map(el => el.textContent.trim()).filter(Boolean)
          : valueEls[0]?.textContent?.trim() || null;

        if (value) {
          facts[factType] = {
            label: label || factType,
            value,
            data_fact_type: factType,
          };
        }
      }
    }

    return Object.keys(facts).length > 0 ? facts : null;
  }

  /**
   * Extract available spaces from the data-fields JSON attribute.
   * This is an embedded JSON array with Space, Size, Term, RentalRate, SpaceUse per space.
   */
  _extractAvailableSpaces() {
    const el = document.querySelector("[data-fields]");
    if (!el) return null;

    const rawAttr = el.getAttribute("data-fields");
    if (!rawAttr) return null;

    try {
      // Unescape HTML entities
      const unescaped = rawAttr
        .replace(/&quot;/g, '"')
        .replace(/&amp;/g, "&")
        .replace(/&#39;/g, "'")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">");

      const parsed = JSON.parse(unescaped);
      if (Array.isArray(parsed) && parsed.length > 0) {
        // Simplify the structure for storage
        return parsed.map(item => ({
          name: item.FeatureName || item.ActualName,
          value: item.FeatureValues?.[0]?.Value || null,
          all_values: item.FeatureValues?.map(fv => ({
            key: fv.Key || null,
            value: fv.Value,
            selected: fv.Selected || false,
          })) || [],
        }));
      }
    } catch (err) {
      this.warn("Failed to parse data-fields JSON", err);
    }

    return null;
  }

  /**
   * Extract full address from breadcrumbs.
   * The last breadcrumb span contains the full address with zip.
   * Example: "667 Madison Ave, New York, NY 10065"
   */
  _extractBreadcrumbAddress() {
    const crumbTitle = document.querySelector(".breadcrumbs__crumb-title");
    if (crumbTitle) {
      // The text may include a link for the zip code — get full text
      return crumbTitle.textContent.trim();
    }
    return null;
  }

  /**
   * Extract broker/contact information.
   */
  _extractBrokerInfo() {
    const contactSection = document.getElementById("contact-form-contacts");
    if (!contactSection) return null;

    const brokers = [];
    const brokerCards = contactSection.querySelectorAll(".broker-card, .contact-card, [class*='broker'], [class*='contact-info']");

    if (brokerCards.length === 0) {
      // Fallback: get all text from the contact section
      const text = contactSection.textContent?.trim();
      if (text) return { raw_text: text };
    }

    for (const card of brokerCards) {
      const name = card.querySelector("[class*='name'], h3, h4, strong")?.textContent?.trim();
      const company = card.querySelector("[class*='company'], [class*='firm']")?.textContent?.trim();
      const phone = card.querySelector("[class*='phone'], a[href^='tel:']")?.textContent?.trim();

      if (name || company) {
        brokers.push({
          name: name || null,
          company: company || null,
          phone: phone || null,
        });
      }
    }

    // Also try the owner logo link
    const ownerLink = document.querySelector(".profile-hero-logo-wrap.owner-logo-container a");
    if (ownerLink) {
      const ownerName = ownerLink.getAttribute("title")?.trim();
      if (ownerName && !brokers.some(b => b.company === ownerName)) {
        brokers.push({
          name: null,
          company: ownerName,
          phone: null,
          source: "owner-logo",
        });
      }
    }

    return brokers.length > 0 ? brokers : null;
  }

  /**
   * Extract listing images from LoopNet's CDN.
   */
  _extractImages() {
    const images = new Set();

    // Primary: og:image
    const ogImg = document.querySelector('meta[property="og:image"]')?.content;
    if (ogImg) images.add(ogImg);

    // High-res listing images from CDN
    const imgEls = document.querySelectorAll('img[src*="images1.loopnet.com"]');
    for (const img of imgEls) {
      const src = img.src || img.getAttribute("data-src");
      if (src && src.includes("LargeHighDefinition")) {
        images.add(src);
      }
    }

    // Also check Large quality if no HighDef found
    if (images.size <= 1) {
      for (const img of imgEls) {
        const src = img.src || img.getAttribute("data-src");
        if (src && src.includes("Large")) {
          images.add(src);
        }
      }
    }

    // Mosaic tiles (lazy-loaded background images)
    const mosaicTiles = document.querySelectorAll(".mosaic-tile[data-src]");
    for (const tile of mosaicTiles) {
      const src = tile.getAttribute("data-src");
      if (src) images.add(src);
    }

    return [...images];
  }

  /**
   * Extract brochure/PDF URL if available.
   */
  _extractBrochureUrl() {
    const pdfEl = document.getElementById("PDFBrochureUri");
    if (pdfEl?.textContent?.trim()) return pdfEl.textContent.trim();
    return null;
  }

  /**
   * Get source type label for diagnostic logging.
   */
  _getSourceType(fieldName) {
    const sourceMap = {
      listing_id: "data-attr",
      listing_type: "data-attr",
      og_title: "meta",
      og_image: "meta",
      hero_address: "DOM",
      hero_subtitle: "DOM",
      property_facts: "DOM+data-attr",
      available_spaces: "embedded-JSON",
      breadcrumb_address: "DOM",
      broker_info: "DOM",
      images: "DOM+meta",
    };
    return sourceMap[fieldName] || "unknown";
  }

  // ── Normalization ──────────────────────────────────────────────────────────

  normalize(raw) {
    const N = SiteRankerNormalize;

    // Parse the subtitle for city, state, zip, property type
    const subtitleParsed = this._parseSubtitle(raw.hero_subtitle);

    // Build full address from hero + subtitle
    const fullAddress = this._buildFullAddress(raw.hero_address, subtitleParsed, raw.breadcrumb_address);
    const parsedAddr = N.parseAddress(fullAddress);

    // Extract rental rate from available spaces
    const rentalRate = this._extractRentalRate(raw.available_spaces);
    const parsedPrice = N.parsePrice(rentalRate);

    // Extract property facts values
    const factVal = (key) => {
      const fact = raw.property_facts?.[key];
      if (!fact) return null;
      return Array.isArray(fact.value) ? fact.value.join(", ") : fact.value;
    };

    // Determine status from listing type
    const statusMap = { FL: "For Lease", FS: "For Sale", FA: "Auction" };
    const status = statusMap[raw.listing_type] || null;

    // Clean og:title to get a better title
    const cleanTitle = this._cleanOgTitle(raw.og_title);

    return {
      source: {
        website: this.siteName,
        url: raw.canonical_url || raw.og_url || window.location.href,
        listing_id: raw.listing_id,
        scraped_at: new Date().toISOString(),
      },
      common: {
        title: cleanTitle,
        address: fullAddress || raw.hero_address,
        city: parsedAddr.city || subtitleParsed.city,
        state: parsedAddr.state || raw.listing_state || subtitleParsed.state,
        zip_code: parsedAddr.zip || subtitleParsed.zip,
        property_type: factVal("BuildingType") || subtitleParsed.property_type,
        price: parsedPrice.value,
        price_text: rentalRate,
        status,
        description: N.clean(raw.og_description || raw.meta_description),
        listing_url: raw.canonical_url || raw.og_url || window.location.href,
        listing_id: raw.listing_id,
        images: raw.images || [],
      },
      website_specific: {
        loopnet: {
          building_class: factVal("BuildingClass"),
          building_height: factVal("BuildingHeight"),
          building_size: factVal("BuildingSize"),
          typical_floor_size: factVal("TypicalFloorSize"),
          year_built: factVal("YearBuiltRenovated"),
          ceiling_height: factVal("UnfinishedCeilingHeight"),
          parking: factVal("Parking"),
          loopnet_rating: factVal("LoopNetRating"),
          listing_type: raw.listing_type,
          available_spaces: raw.available_spaces,
          broker: raw.broker_info,
          brochure_url: raw.brochure_url,
          hero_subtitle: raw.hero_subtitle,
          property_timestamp: raw.property_timestamp,
        },
      },
    };
  }

  /**
   * Parse the hero subtitle to extract city, state, zip, property type, SF range.
   * Example: "6,300 - 48,175 SF of 4-Star Office  Space Available in New York, NY 10065"
   */
  _parseSubtitle(subtitle) {
    const result = { city: null, state: null, zip: null, property_type: null, sf_range: null, rating: null };
    if (!subtitle) return result;

    // Extract SF range: "6,300 - 48,175 SF" or "6,300 SF"
    const sfMatch = subtitle.match(/([\d,]+(?:\s*[-–]\s*[\d,]+)?)\s*SF/i);
    if (sfMatch) result.sf_range = sfMatch[1].trim();

    // Extract property type: "Office", "Retail", "Industrial", etc.
    const typeMatch = subtitle.match(/(?:Star\s+)?(\w+)\s+Space/i);
    if (typeMatch) result.property_type = typeMatch[1].trim();

    // Extract rating: "4-Star"
    const ratingMatch = subtitle.match(/(\d+)-Star/i);
    if (ratingMatch) result.rating = ratingMatch[1] + " Star";

    // Extract city, state, zip: "New York, NY 10065"
    const locationMatch = subtitle.match(/in\s+(.+?),\s*([A-Z]{2})\s*(\d{5})?/);
    if (locationMatch) {
      result.city = locationMatch[1].trim();
      result.state = locationMatch[2].trim();
      result.zip = locationMatch[3]?.trim() || null;
    }

    return result;
  }

  /**
   * Build full address string from available sources.
   */
  _buildFullAddress(heroAddress, subtitleParsed, breadcrumbAddress) {
    // Breadcrumb often has the most complete address
    if (breadcrumbAddress && breadcrumbAddress.includes(",")) {
      return breadcrumbAddress;
    }

    // Combine hero address + city/state/zip from subtitle
    if (heroAddress && subtitleParsed.city) {
      const parts = [heroAddress];
      parts.push(subtitleParsed.city);
      if (subtitleParsed.state) {
        parts.push(subtitleParsed.state + (subtitleParsed.zip ? " " + subtitleParsed.zip : ""));
      }
      // Format: "667 Madison Ave, New York, NY 10065"
      return parts.join(", ");
    }

    return heroAddress || breadcrumbAddress || null;
  }

  /**
   * Extract rental rate from available spaces data.
   */
  _extractRentalRate(spaces) {
    if (!spaces || !Array.isArray(spaces)) return null;

    const rateItem = spaces.find(s =>
      s.name === "Rental Rate" || s.name === "RentalRate" ||
      s.name === "Asking Price" || s.name === "AskingPrice" ||
      s.name === "Sale Price" || s.name === "SalePrice"
    );

    if (rateItem?.value) return rateItem.value;
    return null;
  }

  /**
   * Clean og:title by removing the " | LoopNet" suffix and listing type.
   */
  _cleanOgTitle(ogTitle) {
    if (!ogTitle) return null;
    return ogTitle
      .replace(/\s*\|\s*LoopNet\s*$/i, "")
      .replace(/\s*-\s*(Office|Retail|Industrial|Land|Multifamily|Flex|Special Purpose)\s+(for\s+)?(Lease|Sale|Auction)\s*$/i, "")
      .trim() || null;
  }

  // ── LLM Formatting ─────────────────────────────────────────────────────────

  formatForLLM(normalized) {
    return SiteRankerLLMFormatter.format(normalized);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────

const loopNetAdapter = new LoopNetAdapter();

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => loopNetAdapter.boot());
} else {
  loopNetAdapter.boot();
}
