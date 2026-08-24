/**
 * website-registry.js — Central registry of supported websites
 *
 * Maps hostnames to adapter file names. Used by the manifest to determine
 * which content script to load, and by the popup to identify the source site.
 *
 * Adding a new site:
 *   1. Create the adapter file (content-{sitename}.js)
 *   2. Add an entry here
 *   3. Add to manifest.json content_scripts
 */

"use strict";

const SiteRankerRegistry = {
  sites: [
    {
      name: "crexi",
      displayName: "Crexi",
      hostnames: ["www.crexi.com", "crexi.com"],
      contentScript: "content-crexi.js",
      color: "#6366f1",  // Indigo
    },
    {
      name: "loopnet",
      displayName: "LoopNet",
      hostnames: ["www.loopnet.com", "loopnet.com"],
      contentScript: "content-loopnet.js",
      color: "#ef4444",  // Red (LoopNet brand)
    },
    {
      name: "zillow",
      displayName: "Zillow",
      hostnames: ["www.zillow.com", "zillow.com"],
      contentScript: "content-zillow.js",
      color: "#3b82f6",  // Blue (Zillow brand)
      disabled: true,    // Not yet implemented
    },
  ],

  /**
   * Find the site entry for a given hostname.
   * @param {string} hostname - e.g. "www.loopnet.com"
   * @returns {object|null}
   */
  findByHostname(hostname) {
    const h = hostname.toLowerCase();
    return this.sites.find(s => !s.disabled && s.hostnames.includes(h)) || null;
  },

  /**
   * Find the site entry by name.
   * @param {string} name - e.g. "crexi"
   * @returns {object|null}
   */
  findByName(name) {
    return this.sites.find(s => s.name === name) || null;
  },

  /**
   * Get all active (non-disabled) sites.
   * @returns {object[]}
   */
  getActiveSites() {
    return this.sites.filter(s => !s.disabled);
  },

  /**
   * Determine which site the current URL belongs to.
   * @param {string} url
   * @returns {object|null}
   */
  identifyFromUrl(url) {
    try {
      const hostname = new URL(url).hostname.toLowerCase();
      return this.findByHostname(hostname);
    } catch {
      return null;
    }
  },

  /**
   * Capability matrix — which common fields each site supports.
   * Updated as adapters are built.
   */
  capabilities: {
    crexi: {
      title: true,
      address: true,
      price: true,
      property_type: false,
      description: true,
      images: true,
      cap_rate: true,
      noi: true,
      sqft: true,
      year_built: true,
      broker: false,
    },
    loopnet: {
      title: true,
      address: true,
      price: true,
      property_type: true,
      description: true,
      images: true,
      cap_rate: false,
      noi: false,
      sqft: true,
      year_built: true,
      broker: true,
      building_class: true,
      building_height: true,
      parking: true,
    },
  },
};

if (typeof window !== "undefined") {
  window.SiteRankerRegistry = SiteRankerRegistry;
}
