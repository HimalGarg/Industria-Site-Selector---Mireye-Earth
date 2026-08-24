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
});
