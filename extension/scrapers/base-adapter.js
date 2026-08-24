/**
 * base-adapter.js — Base Adapter for Site Ranker multi-site scraping
 *
 * All website adapters extend this class and implement the standard interface.
 * The base class provides:
 *   - Common button injection & styling
 *   - Shared click handler flow (extract → store → POST)
 *   - MutationObserver SPA navigation handling
 *   - Structured logging
 *
 * Subclasses must implement:
 *   - siteName        (string)
 *   - hostnames        (string[])
 *   - isListingPage()  → boolean
 *   - getAnchorElement() → Element|null  (where to inject button)
 *   - extractRaw()     → object
 *   - normalize(raw)   → { source, common, website_specific }
 *   - formatForLLM(normalized) → object
 */

"use strict";

class BaseAdapter {
  constructor() {
    this.SESSION_KEY = "siteRankerSessionId";
    this.CAPTURE_KEY = "lastCapture";
    this.INJECT_ATTR = "data-sr-injected";
    this.OBSERVER_TIMEOUT_MS = 10000;
    this.DEBUG = true;
  }

  // ── Must Override ──────────────────────────────────────────────────────────

  /** @returns {string} Short site identifier (e.g. "crexi", "loopnet") */
  get siteName() { throw new Error("siteName not implemented"); }

  /** @returns {string[]} Hostnames this adapter handles */
  get hostnames() { throw new Error("hostnames not implemented"); }

  /** @returns {boolean} Whether the current page is a listing detail page */
  isListingPage() { throw new Error("isListingPage() not implemented"); }

  /** @returns {Element|null} DOM element to anchor the button near */
  getAnchorElement() { throw new Error("getAnchorElement() not implemented"); }

  /** @returns {object} Raw extracted data, as close to source as possible */
  extractRaw() { throw new Error("extractRaw() not implemented"); }

  /**
   * Normalize raw data into common + website_specific fields.
   * @param {object} raw - Output of extractRaw()
   * @returns {{ source: object, common: object, website_specific: object }}
   */
  normalize(raw) { throw new Error("normalize() not implemented"); }

  /**
   * Format normalized data for LLM consumption.
   * @param {object} normalized - Output of normalize()
   * @returns {object}
   */
  formatForLLM(normalized) { throw new Error("formatForLLM() not implemented"); }

  // ── Public API ─────────────────────────────────────────────────────────────

  /** Full scrape pipeline: raw → normalize → LLM → wrap with diagnostics */
  scrape() {
    const startTime = performance.now();
    const raw = this.extractRaw();
    const normalized = this.normalize(raw);
    const llm = this.formatForLLM(normalized);
    const elapsed = Math.round(performance.now() - startTime);

    // Count fields
    const commonKeys = Object.keys(normalized.common || {});
    const fieldsFound = commonKeys.filter(k => normalized.common[k] != null && normalized.common[k] !== "").length;
    const fieldsMissing = commonKeys.length - fieldsFound;

    const result = {
      source: normalized.source,
      common: normalized.common,
      website_specific: normalized.website_specific,
      raw,
      llm,
      meta: {
        website: this.siteName,
        success: fieldsFound > 0,
        fields_found: fieldsFound,
        fields_missing: fieldsMissing,
        scraped_at: new Date().toISOString(),
        extraction_ms: elapsed,
        parser_version: "2.0.0",
      },
    };

    this.log("Scrape complete", {
      fields_found: fieldsFound,
      fields_missing: fieldsMissing,
      elapsed_ms: elapsed,
    });

    return result;
  }

  /** Boot the adapter: check page, inject button, watch for SPA nav */
  boot() {
    if (this.isListingPage()) {
      this._waitForAnchor();
    }
    this._watchNavigation();
  }

  // ── Logging ────────────────────────────────────────────────────────────────

  log(message, data = null) {
    if (!this.DEBUG) return;
    const prefix = `[Site Ranker][${this.siteName}]`;
    if (data) {
      console.log(`${prefix} ${message}`, data);
    } else {
      console.log(`${prefix} ${message}`);
    }
  }

  logField(fieldName, status, source = null) {
    if (!this.DEBUG) return;
    const prefix = `[Site Ranker][${this.siteName}]`;
    const srcStr = source ? ` (${source})` : "";
    console.log(`${prefix}   ${status === "FOUND" ? "✓" : "✗"} ${fieldName}${srcStr}`);
  }

  warn(message, data = null) {
    const prefix = `[Site Ranker][${this.siteName}]`;
    if (data) {
      console.warn(`${prefix} ${message}`, data);
    } else {
      console.warn(`${prefix} ${message}`);
    }
  }

  // ── Button Injection & Styling ─────────────────────────────────────────────

  _injectStyles() {
    if (document.getElementById("sr-adapter-styles")) return;
    const style = document.createElement("style");
    style.id = "sr-adapter-styles";
    style.textContent = `
      .sr-btn-wrap {
        display: inline-flex;
        align-items: center;
        margin: 8px 0 12px;
      }
      #sr-capture-btn {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 9px 18px;
        background: rgba(21, 28, 40, 0.85);
        backdrop-filter: blur(12px);
        color: #4EDEA3;
        border: 1px solid rgba(78, 222, 163, 0.4);
        border-radius: 8px;
        font-family: 'Outfit', 'Inter', system-ui, -apple-system, sans-serif;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        letter-spacing: 0.01em;
        transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 15px rgba(78, 222, 163, 0.15);
        z-index: 999;
      }
      #sr-capture-btn:hover {
        background: rgba(28, 32, 40, 0.95);
        border-color: #4EDEA3;
        box-shadow: 0 6px 25px rgba(0, 0, 0, 0.5), 0 0 25px rgba(78, 222, 163, 0.35);
        transform: translateY(-2px);
      }
      #sr-capture-btn:active {
        transform: translateY(0) scale(0.98);
      }
      #sr-capture-btn:disabled {
        opacity: 0.6;
        cursor: wait;
      }
      #sr-capture-btn svg {
        width: 16px;
        height: 16px;
        flex-shrink: 0;
      }
      #sr-capture-btn.sr-success {
        border-color: #10B981;
        color: #4EDEA3;
        background: rgba(16, 185, 129, 0.2);
        box-shadow: 0 0 20px rgba(78, 222, 163, 0.4);
      }
      #sr-capture-btn.sr-error {
        border-color: #FFB4AB;
        color: #FFB4AB;
        background: rgba(147, 0, 10, 0.4);
      }
      .sr-site-badge {
        font-size: 9px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 1px 5px;
        border-radius: 3px;
        background: rgba(0, 212, 180, 0.15);
        color: #00d4b4;
        margin-left: 2px;
      }
    `;
    document.head.appendChild(style);
  }

  _createButton() {
    const btn = document.createElement("button");
    btn.id = "sr-capture-btn";
    btn.title = "Capture this listing for Site Ranker";
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
        <circle cx="12" cy="10" r="3"/>
      </svg>
      <span class="sr-btn-label">Add to Site Ranker</span>
      <span class="sr-site-badge">${this.siteName}</span>
    `;
    return btn;
  }

  _setBtnState(btn, state, label) {
    btn.className = state !== "idle" ? `sr-${state}` : "";
    btn.disabled = state === "loading";
    const lbl = btn.querySelector(".sr-btn-label");
    if (lbl) {
      lbl.textContent =
        state === "loading" ? "Capturing…" :
        label               ? label        :
                              "Add to Site Ranker";
    }
  }

  async _handleBtnClick(btn) {
    this._setBtnState(btn, "loading");

    const sessionId = await new Promise(res =>
      chrome.storage.local.get(this.SESSION_KEY, d => res(d[this.SESSION_KEY] || null))
    );

    const scraped = this.scrape();
    const { common, source } = scraped;

    if (!common.address && !common.title) {
      this._setBtnState(btn, "error", "Couldn't detect listing");
      setTimeout(() => this._setBtnState(btn, "idle"), 4000);
      return;
    }

    // Build capture data compatible with existing popup.js flow
    const captureData = {
      address: common.address || null,
      listing_title: common.title || null,
      price: common.price_text || common.price || null,
      image_url: (common.images && common.images[0]) || null,
      details: {
        ...scraped.website_specific?.[this.siteName] || {},
        ...(common.description ? { description: common.description } : {}),
      },
      source_url: common.listing_url || source?.url || window.location.href,
      source_website: this.siteName,
      // Preserve full structured data for future use
      _scraped: scraped,
    };

    // Save for popup pre-fill
    await chrome.storage.local.set({ [this.CAPTURE_KEY]: captureData });

    if (!sessionId) {
      this._setBtnState(btn, "error", "Connect session via popup");
      setTimeout(() => this._setBtnState(btn, "idle"), 4000);
      return;
    }

    // Build POST payload
    const addressStr = captureData.address || captureData.listing_title || "Unknown address";
    const payload = {
      session_id: sessionId,
      address: addressStr,
      source_url: captureData.source_url,
      listing_title: captureData.listing_title || undefined,
      image_url: captureData.image_url || undefined,
      details: captureData.details || undefined,
    };

    if (captureData.price) {
      payload.details = { ...(payload.details || {}), price: captureData.price };
    }

    try {
      const res = await fetch("http://localhost:8000/cart-items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}`);
      }

      const result = await res.json();
      this.log("POST success", result);
      this._setBtnState(btn, "success", "Added to Cart ✓");
      setTimeout(() => this._setBtnState(btn, "idle"), 4000);
    } catch (err) {
      console.error(`[Site Ranker][${this.siteName}] POST failed:`, err);
      this._setBtnState(btn, "error", "Backend offline — check server");
      setTimeout(() => this._setBtnState(btn, "idle"), 4000);
    }
  }

  _injectButton() {
    if (document.getElementById("sr-capture-btn")) return;

    const anchor = this.getAnchorElement();
    if (!anchor) return;

    const wrap = document.createElement("div");
    wrap.className = "sr-btn-wrap";

    const btn = this._createButton();
    btn.addEventListener("click", e => {
      e.preventDefault();
      e.stopPropagation();
      this._handleBtnClick(btn);
    });

    wrap.appendChild(btn);
    anchor.appendChild(wrap);
    this.log("Button injected");
  }

  // ── MutationObserver ───────────────────────────────────────────────────────

  _waitForAnchor() {
    if (this.getAnchorElement()) {
      this._injectStyles();
      this._injectButton();
      return;
    }

    const observer = new MutationObserver(() => {
      if (this.getAnchorElement()) {
        observer.disconnect();
        this._injectStyles();
        this._injectButton();
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => observer.disconnect(), this.OBSERVER_TIMEOUT_MS);
  }

  _watchNavigation() {
    let lastUrl = location.href;
    const navObserver = new MutationObserver(() => {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        document.getElementById("sr-capture-btn")?.closest(".sr-btn-wrap")?.remove();
        if (this.isListingPage()) {
          this._waitForAnchor();
        }
      }
    });
    navObserver.observe(document.body, { childList: true, subtree: true });
  }
}

// Make available for content scripts (no module system in MV3 content scripts)
if (typeof window !== "undefined") {
  window.SiteRankerBaseAdapter = BaseAdapter;
}
