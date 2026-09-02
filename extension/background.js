/**
 * background.js — Site Ranker Capture service worker
 *
 * Responsibilities:
 *  1. Receive session_id relayed by content-session.js (running on the website)
 *     and persist it to chrome.storage.local.
 *  2. Act as the message relay hub so content scripts can reach storage
 *     without needing direct storage access themselves.
 */

const SESSION_KEY = "siteRankerSessionId";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SESSION_ID_FOUND" && message.sessionId) {
    chrome.storage.local.set({ [SESSION_KEY]: message.sessionId }, () => {
      console.log(
        "[Site Ranker] Session ID stored from website:",
        message.sessionId
      );
      sendResponse({ ok: true });
    });
    // Return true to indicate we will respond asynchronously
    return true;
  }

  if (message.type === "FETCH_RADIUS") {
    console.log("Starting Robust Web Agent DOM Scraper on Crexi...");
    
    // The previous failure was caused by passing the exact street address, 
    // which caused Crexi to bypass the search page and redirect to a single listing,
    // OR caused LoopNet to 404 due to strict URL routing rules.
    // FIX: We will ONLY search the Zip Code or City/State to guarantee a multi-property search page.
    let searchTerm = "";
    const zipMatch = message.address ? message.address.match(/\b\d{5}\b/) : null;
    if (zipMatch) {
      searchTerm = zipMatch[0]; // e.g., "94804" or "14607"
    } else if (message.address) {
      // Strip out the street address by splitting at the first comma (e.g., "1170 23rd St, Richmond, CA" -> "Richmond, CA")
      const parts = message.address.split(',');
      if (parts.length > 1) {
        searchTerm = parts.slice(1).join(',').trim();
      } else {
        searchTerm = message.address;
      }
    } else {
      searchTerm = "CA";
    }
    
    // Using Crexi's text search parameter guarantees no 404s (since it's a query param) 
    // and using just the zip/city guarantees it won't redirect to a single property.
    const searchUrl = `https://www.crexi.com/search?searchAttributes.status_tree_Active=&keywords_value=${encodeURIComponent(searchTerm)}&searchType=Sales`;
    
    // Active tab bypasses Cloudflare background-tab detection
    chrome.tabs.create({ url: searchUrl, active: true }, (tab) => {
      const tabId = tab.id;
      
      const listener = (tid, changeInfo) => {
        if (tid === tabId && changeInfo.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          
          chrome.scripting.executeScript({
              target: { tabId: tabId },
              func: async () => {
                // Wait 6 seconds for Crexi SPA to fully render (it's an Angular app)
                await new Promise(resolve => setTimeout(resolve, 6000));
                
                const waitForElements = () => new Promise(resolve => {
                  let attempts = 0;
                  const interval = setInterval(() => {
                    attempts++;
                    
                    // Check for CAPTCHA / bot detection
                    const pageText = document.body.innerText || "";
                    const isCaptcha = pageText.includes("Just a moment") || 
                                      pageText.includes("Security check") ||
                                      pageText.includes("Enable JavaScript");
                    if (isCaptcha) {
                      attempts--; // Pause timeout — let user solve it
                      return;
                    }
                    
                    // ── Selector Strategy (Crexi 2025 DOM) ──────────────────
                    // Strategy 1: Named property card components
                    const cardSelectors = [
                      'crx-property-card',
                      'app-property-card', 
                      '[data-cy="propertyCard"]',
                      '.property-card-wrapper',
                      'article[class*="property"]',
                      '.listing-card',
                    ];
                    let cards = [];
                    for (const sel of cardSelectors) {
                      const found = Array.from(document.querySelectorAll(sel));
                      if (found.length > 0) { cards = found; break; }
                    }

                    // Strategy 2: Anchor links to property detail pages
                    // Crexi property URLs look like: /properties/{id}-{address-slug}
                    // MUST contain a numeric ID component
                    const allLinks = Array.from(document.querySelectorAll('a[href]'));
                    const listingLinks = allLinks.filter(a => {
                      const href = a.href ? a.href.toLowerCase() : "";
                      if (!href.includes('/properties/') && !href.includes('/businesses/') && !href.includes('/lease/')) return false;
                      if (href.includes('?search')) return false;
                      return true;
                    });
                    
                    // Wait up to 25 seconds for heavy React/Angular loads
                    if (cards.length > 0 || listingLinks.length > 2 || attempts > 50) {
                      clearInterval(interval);
                      
                      const properties = [];

                      // ── Extract from card components ─────────────────────
                      if (cards.length > 0) {
                        cards.forEach(card => {
                          const titleEl = card.querySelector(
                            '[data-cy="title"], .property-name, h4, h3, .card-title, [class*="title"]'
                          );
                          const addressEl = card.querySelector(
                            '[data-cy="address"], .property-address, .address, [class*="address"], [class*="location"]'
                          );
                          const priceEl = card.querySelector(
                            '[data-cy="price"], .crx-price, .price, [class*="price"], [class*="asking"]'
                          );
                          const linkEl = card.querySelector('a[href*="/properties/"]') || card.querySelector('a');
                          const imageEl = card.querySelector('img');

                          const rawAddress = addressEl ? addressEl.textContent.trim() : "";
                          const rawTitle = titleEl ? titleEl.textContent.trim() : "";
                          const rawPrice = priceEl ? priceEl.textContent.trim() : "";
                          const href = linkEl ? (linkEl.href.startsWith("http") ? linkEl.href : `https://www.crexi.com${linkEl.getAttribute("href")}`) : "";
                          const imgSrc = imageEl ? imageEl.src : "";

                          // Validate: must have something that looks like an address
                          if (!rawAddress && !rawTitle && !href.includes('/properties/')) return;

                          properties.push({
                            address: rawAddress || "Nearby Property",
                            listing_title: rawTitle || rawAddress || "Radius Comparable",
                            source_url: href || window.location.href,
                            image_url: imgSrc || undefined,
                            details: { price: rawPrice || "See Listing" }
                          });
                        });
                      }

                      // ── Fallback: extract from validated property links ───
                      if (properties.length === 0 && listingLinks.length > 0) {
                        const seenIds = new Set();
                        listingLinks.forEach(a => {
                          const href = a.href;

                          // Parse address from slug: /properties/12345-1234-main-st-chicago-il
                          const pathPart = href.split('/properties/')[1] || "";
                          const slug = pathPart.split('?')[0].split('#')[0];
                          
                          // Slug must contain digits to be a real listing
                          if (!/\d/.test(slug)) return;

                          // Dedupe by numeric ID (e.g. from "12345/ohio" or "12345-main-st")
                          const slugParts = slug.split('-');
                          const firstPart = slugParts[0];
                          const numericMatch = firstPart.match(/\d+/);
                          const propId = numericMatch ? numericMatch[0] : href;

                          if (seenIds.has(propId)) return;
                          seenIds.add(propId);

                          // Convert slug to readable address: "1234-main-st-chicago-il" → "1234 main st chicago il"
                          // Remove leading numeric ID prefix if present
                          const startIdx = (slugParts[0].length > 5 && /^\d+$/.test(slugParts[0])) ? 1 : 0;
                          const addressSlug = slugParts.slice(startIdx).join(' ');

                          // Capitalize each word
                          const parsedAddress = addressSlug.replace(/\b\w/g, c => c.toUpperCase());

                          // Extract text content for price
                          const textContent = a.innerText.trim();
                          let price = "See Listing";
                          const priceMatch = textContent.match(/\$[\d,\.]+[MmKk]?/);
                          if (priceMatch) price = priceMatch[0];

                          properties.push({
                            address: parsedAddress,
                            listing_title: textContent.slice(0, 80) || parsedAddress,
                            source_url: href,
                            details: { price }
                          });
                        });
                      }

                      resolve(properties);
                    }
                  }, 500);
                });
                
                return await waitForElements();
              }
          }).then((results) => {
            chrome.tabs.remove(tabId).catch(() => {});
            
            if (!results || results.length === 0 || !results[0].result || results[0].result.length === 0) {
              console.error("No properties found in DOM after 25 seconds.");
              return;
            }
            
            // Deduplicate by source_url and keep up to 30 candidates
            const rawProps = results[0].result;
            const uniqueProps = Array.from(
              new Map(rawProps.map(p => [p.source_url || p.address, p])).values()
            ).slice(0, 30);
            
            // POST directly from background script so it survives the popup closing!
            fetch(`http://localhost:8000/cart-items/${message.parent_id}/radius-search`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ 
                session_id: message.session_id, 
                properties: uniqueProps,
                parent_lat: message.lat,
                parent_lng: message.lng
              })
            }).then(res => res.json())
              .then(data => console.log("Successfully posted radius properties:", data))
              .catch(err => console.error("Failed to post radius properties:", err));
              
          }).catch(err => {
            chrome.tabs.remove(tabId).catch(() => {});
            console.error("Scraper error:", err.message);
          });
        }
      };
      
      chrome.tabs.onUpdated.addListener(listener);
      
      setTimeout(() => {
        chrome.tabs.onUpdated.removeListener(listener);
        chrome.tabs.remove(tabId).catch(() => {});
      }, 40000); // 40 second generous timeout
    });
    
    // Return immediately to the popup so it doesn't hang
    sendResponse({ ok: true, message: "Started background scraper" });
    return true;
  }
});
