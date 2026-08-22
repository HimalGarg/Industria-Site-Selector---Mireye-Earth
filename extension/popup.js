/**
 * popup.js — Site Ranker Capture popup logic (v2 Multi-Site)
 *
 * Flow:
 *  1. On open: check chrome.storage.local for siteRankerSessionId.
 *  2. No session  → show "connect" view.
 *  3. Has session → show "capture" view, pre-fill from lastCapture (auto-extract
 *                   from Crexi, LoopNet, or other supported sites) or
 *                   lastSelection (manual highlight), fetch recent cart items.
 *  4. Submit: POST /cart-items with address + optional listing_title/details,
 *             refresh list, show inline status.
 *  5. Disconnect: clears stored session ID, switches back to connect view.
 */

"use strict";

// ── Config ──────────────────────────────────────────────────────────────────
const API_BASE      = "http://localhost:8000";
const SESSION_KEY   = "siteRankerSessionId";
const SELECTION_KEY = "lastSelection";
const CAPTURE_KEY   = "lastCapture";   // set by any site adapter on capture
const MAX_RECENT    = 5;

// Site display config (colors + labels)
const SITE_CONFIG = {
  crexi:   { label: "Crexi",   color: "#6366f1" },
  loopnet: { label: "LoopNet", color: "#ef4444" },
  zillow:  { label: "Zillow",  color: "#3b82f6" },
};

// TODO (deploy): update WEBSITE_URL to the real domain once it's live.
const WEBSITE_URL   = "http://localhost:3000";

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Generate a random UUID-like session ID. */
function generateSessionId() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Format an ISO timestamp to a short, human-readable string. */
function formatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
           " " +
           d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

/** Extract a readable hostname from a URL string, or return the raw URL. */
function shortUrl(url) {
  if (!url) return "—";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.length > 40 ? url.slice(0, 40) + "…" : url;
  }
}

function setStatus(msg, type = "") {
  const el = document.getElementById("status-line");
  el.textContent = msg;
  el.className = type;
}

function escHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── DOM refs ─────────────────────────────────────────────────────────────────
const loadingOverlay  = document.getElementById("loading-overlay");
const mainBody        = document.getElementById("main-body");
const viewConnect     = document.getElementById("view-connect");
const viewCapture     = document.getElementById("view-capture");
const sessionFooter   = document.getElementById("session-footer");
const sessionDisplay  = document.getElementById("session-id-display");
const addressInput    = document.getElementById("address-input");
const clearBtn        = document.getElementById("clear-input");
const sourceUrlRow    = document.getElementById("source-url-row");
const sourceUrlDisplay= document.getElementById("source-url-display");
const submitBtn       = document.getElementById("btn-submit");
const submitLabel     = document.getElementById("submit-label");
const submitSpinner   = document.getElementById("submit-spinner");
const submitIcon      = document.getElementById("submit-icon");
const recentList      = document.getElementById("recent-list");
const recentCount     = document.getElementById("recent-count");
const connectBtn      = document.getElementById("btn-connect");
const disconnectBtn   = document.getElementById("btn-disconnect");

// ── State ────────────────────────────────────────────────────────────────────
let currentSessionId    = null;
let currentTabUrl       = null;
let currentCaptureData  = null; // enriched data from lastCapture (Crexi PDP)

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  // Read active tab URL (needed for source_url on submit)
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentTabUrl = tab?.url || null;
  } catch {
    currentTabUrl = null;
  }

  // Load session + capture + selection in parallel
  chrome.storage.local.get([SESSION_KEY, CAPTURE_KEY, SELECTION_KEY], (data) => {
    const sessionId   = data[SESSION_KEY] || null;
    const capture     = data[CAPTURE_KEY] || null;   // from Crexi PDP auto-extract
    const selection   = data[SELECTION_KEY] || "";   // from manual text highlight

    loadingOverlay.classList.remove("active");
    mainBody.style.display = "block";

    if (!sessionId) {
      showConnectView();
    } else {
      showCaptureView(sessionId, capture, selection);
    }
  });
}

// ── Views ─────────────────────────────────────────────────────────────────────

function showConnectView() {
  currentSessionId   = null;
  currentCaptureData = null;
  viewConnect.classList.add("active");
  viewCapture.classList.remove("active");
  sessionFooter.style.display = "none";
}

/**
 * Show the capture view, pre-filling from:
 *  1. capture (lastCapture — Crexi PDP auto-extract) — takes priority
 *  2. selection (lastSelection — manual text highlight) — fallback
 */
function showCaptureView(sessionId, capture = null, selection = "") {
  currentSessionId = sessionId;
  viewConnect.classList.remove("active");
  viewCapture.classList.add("active");

  // Session footer
  sessionFooter.style.display = "flex";
  sessionDisplay.textContent = "Session: " + sessionId.slice(0, 18) + "…";

  // Determine pre-fill value and source URL
  if (capture && (capture.address || capture.listing_title)) {
    // Auto-extracted from a supported site — use it
    currentCaptureData = capture;
    const displayAddr = [capture.address, capture.listing_title]
      .filter(Boolean)
      .join(" — ");
    addressInput.value = displayAddr || "";

    // Show the listing's canonical URL if available
    const displayUrl = capture.source_url || currentTabUrl;
    if (displayUrl) {
      const siteCfg = SITE_CONFIG[capture.source_website] || null;
      const siteLabel = siteCfg ? `<span class="source-site-badge" style="background:${siteCfg.color}">${siteCfg.label}</span> ` : "";
      sourceUrlDisplay.innerHTML = siteLabel + escHtml(shortUrl(displayUrl));
      sourceUrlRow.style.display = "flex";
    } else {
      sourceUrlRow.style.display = "none";
    }

    // Show an auto-detect badge with site name
    const siteName = SITE_CONFIG[capture.source_website]?.label || "listing";
    if (!capture.address) {
      setStatus("⚠ Couldn't auto-detect address — please enter it manually.", "error");
    } else {
      setStatus(`✦ Auto-captured from ${siteName} — edit if needed.`, "");
    }
  } else {
    // Manual selection or fresh open
    currentCaptureData = null;
    addressInput.value = selection;

    if (currentTabUrl) {
      sourceUrlDisplay.textContent = shortUrl(currentTabUrl);
      sourceUrlRow.style.display = "flex";
    } else {
      sourceUrlRow.style.display = "none";
    }
  }

  toggleClear();

  // Load recent items
  loadRecentItems(sessionId);
}

// ── Connect flow ──────────────────────────────────────────────────────────────

connectBtn.addEventListener("click", () => {
  const newId = generateSessionId();
  chrome.storage.local.set({ [SESSION_KEY]: newId }, () => {
    const url = `${WEBSITE_URL}/?session=${newId}`;
    chrome.tabs.create({ url });
    // Switch to capture view now — the website will adopt this session ID on load
    showCaptureView(newId, null, "");
  });
});

// ── Disconnect ────────────────────────────────────────────────────────────────

disconnectBtn.addEventListener("click", () => {
  if (!confirm("Disconnect this session? You'll need to reconnect to add items to your cart.")) return;
  chrome.storage.local.remove([SESSION_KEY, SELECTION_KEY, CAPTURE_KEY], () => {
    currentCaptureData = null;
    recentList.innerHTML = "";
    setStatus("");
    showConnectView();
  });
});

// ── Address input ─────────────────────────────────────────────────────────────

addressInput.addEventListener("input", () => {
  toggleClear();
  setStatus(""); // clear error on edit
  // User is editing — discard auto-capture metadata so submit uses typed value
  if (currentCaptureData) currentCaptureData = null;
});

clearBtn.addEventListener("click", () => {
  addressInput.value = "";
  toggleClear();
  addressInput.focus();
  currentCaptureData = null;
  chrome.storage.local.remove([SELECTION_KEY, CAPTURE_KEY]);
  setStatus("");
});

function toggleClear() {
  if (addressInput.value.trim()) {
    clearBtn.classList.add("visible");
  } else {
    clearBtn.classList.remove("visible");
  }
}

// ── Submit ────────────────────────────────────────────────────────────────────

submitBtn.addEventListener("click", handleSubmit);

// Allow Ctrl+Enter / Cmd+Enter to submit from textarea
addressInput.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    handleSubmit();
  }
});

async function handleSubmit() {
  const address = addressInput.value.trim();

  if (!address) {
    setStatus("⚠ Please enter or highlight an address first.", "error");
    addressInput.focus();
    return;
  }

  if (!currentSessionId) {
    setStatus("⚠ No active session. Please connect first.", "error");
    return;
  }

  setLoading(true);
  setStatus("");

  // Build payload — include enriched fields from auto-extract if available
  const payload = {
    session_id: currentSessionId,
    address,
  };

  // source_url: prefer capture's canonical URL over active tab URL
  const sourceUrl = currentCaptureData?.source_url || currentTabUrl || undefined;
  if (sourceUrl) payload.source_url = sourceUrl;

  // listing_title, image_url, and details — only from auto-extract (not manual selection)
  if (currentCaptureData) {
    if (currentCaptureData.listing_title) {
      payload.listing_title = currentCaptureData.listing_title;
    }
    if (currentCaptureData.image_url) {
      payload.image_url = currentCaptureData.image_url;
    }
    if (currentCaptureData.details) {
      payload.details = currentCaptureData.details;
    }
    if (currentCaptureData.price) {
      // Merge price into details object
      payload.details = { ...(payload.details || {}), price: currentCaptureData.price };
    }
  }

  try {
    const res = await fetch(`${API_BASE}/cart-items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    // Success — clear input, clear stored data, refresh list
    addressInput.value = "";
    toggleClear();
    currentCaptureData = null;
    chrome.storage.local.remove([SELECTION_KEY, CAPTURE_KEY]);
    setStatus("✓ Added to cart!", "success");
    await loadRecentItems(currentSessionId);

    // Auto-clear success message after 3 s
    setTimeout(() => setStatus(""), 3000);
  } catch (err) {
    const msg = err.message.includes("Failed to fetch")
      ? "⚠ Cannot reach the backend. Is it running on port 8000?"
      : `⚠ ${err.message}`;
    setStatus(msg, "error");
  } finally {
    setLoading(false);
  }
}

function setLoading(on) {
  submitBtn.disabled = on;
  submitLabel.textContent = on ? "Adding…" : "Add to Cart";
  submitSpinner.style.display = on ? "block" : "none";
  submitIcon.style.display    = on ? "none"  : "block";
}

// ── Recent items ──────────────────────────────────────────────────────────────

async function loadRecentItems(sessionId) {
  try {
    const res = await fetch(
      `${API_BASE}/cart-items?session_id=${encodeURIComponent(sessionId)}`
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const items = await res.json();
    renderRecentItems(items.slice(0, MAX_RECENT));
  } catch {
    // Silent — not critical; don't overwrite the submit status message
    renderRecentItems([]);
  }
}

function renderRecentItems(items) {
  recentCount.textContent = items.length > 0 ? `${items.length} item${items.length !== 1 ? "s" : ""}` : "0 items";

  if (items.length === 0) {
    recentList.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="3"/>
          <path d="M9 12h6M12 9v6"/>
        </svg>
        <div>No captures yet — highlight an<br>address on a listing page to start.</div>
      </div>`;
    return;
  }

  recentList.innerHTML = items
    .map(
      (item) => {
        // Collect detail tags — support both Crexi and LoopNet fields
        const tags = [];
        const d = item.details || {};

        // Price (common)
        if (d["price"]) tags.push(d["price"]);
        else if (d["Asking Price"]) tags.push(d["Asking Price"]);

        // Crexi-specific
        if (d["Cap Rate"]) tags.push(`Cap: ${d["Cap Rate"]}`);
        if (d["NOI"]) tags.push(`NOI: ${d["NOI"]}`);

        // Size (common across sites)
        if (d["Square Footage"]) tags.push(d["Square Footage"]);
        else if (d["Building Size"]) tags.push(d["Building Size"]);
        else if (d["building_size"]) tags.push(d["building_size"]);

        // LoopNet-specific
        if (d["building_class"]) tags.push(`Class ${d["building_class"]}`);
        if (d["year_built"]) tags.push(`Built ${d["year_built"]}`);

        const tagsHtml = tags.length
          ? `<div class="item-tags">${tags.slice(0, 4).map(t => `<span class="item-tag">${escHtml(t)}</span>`).join("")}</div>`
          : "";

        const imgHtml = item.image_url
          ? `<img class="item-thumb" src="${escHtml(item.image_url)}" alt="Listing" onerror="this.style.display='none'" />`
          : `<div class="item-dot"></div>`;

        // Detect source site from URL for badge
        const sourceSite = detectSiteFromUrl(item.source_url);
        const siteBadge = sourceSite
          ? `<span class="item-site-badge" style="background:${sourceSite.color}">${sourceSite.label}</span>`
          : "";

        return `
        <div class="item-card">
          ${imgHtml}
          <div class="item-content">
            <div class="item-address" title="${escHtml(item.address)}">${escHtml(
              item.listing_title ? item.listing_title : item.address
            )}</div>
            <div class="item-sub">${escHtml(item.listing_title ? item.address : "")}</div>
            ${tagsHtml}
            <div class="item-meta">
              <span>${formatDate(item.added_at)}</span>
              ${siteBadge}
              ${item.source_url ? `<span class="item-source" title="${escHtml(item.source_url)}">${escHtml(shortUrl(item.source_url))}</span>` : ""}
            </div>
          </div>
        </div>`;
      }
    )
    .join("");
}

// ── Helpers (multi-site) ─────────────────────────────────────────────────────

function detectSiteFromUrl(url) {
  if (!url) return null;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    if (hostname.includes("crexi.com")) return SITE_CONFIG.crexi;
    if (hostname.includes("loopnet.com")) return SITE_CONFIG.loopnet;
    if (hostname.includes("zillow.com")) return SITE_CONFIG.zillow;
  } catch {}
  return null;
}

// ── Boot ──────────────────────────────────────────────────────────────────────
init();
