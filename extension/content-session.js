/**
 * content-session.js — runs on the Site Ranker website (localhost / real domain)
 *
 * On page load, reads the session_id from the website's localStorage and
 * relays it to background.js which stores it in chrome.storage.local.
 *
 * This is the "primary path" from the session model: the website owns the
 * session_id, and the extension adopts it so cart items land in the right
 * place.
 *
 * TODO (deploy): update manifest.json content_scripts matches to include
 *               the real production domain when the website goes live.
 */

const SESSION_KEY = "session_id"; // localStorage key used by the website

(function syncSession() {
  const sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    // Website hasn't generated a session yet — nothing to relay.
    return;
  }

  chrome.runtime.sendMessage(
    { type: "SESSION_ID_FOUND", sessionId },
    (response) => {
      if (chrome.runtime.lastError) {
        // Extension may not be active — silently ignore.
        return;
      }
      console.log("[Site Ranker] Session synced to extension:", sessionId);
    }
  );
})();
