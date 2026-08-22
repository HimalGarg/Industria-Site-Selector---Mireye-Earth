/**
 * content.js — runs on LoopNet and Crexi
 *
 * Listens for mouseup events. When the user finishes selecting text,
 * it reads the raw selection (no DOM parsing, no format validation)
 * and stores it in chrome.storage.local under "lastSelection".
 *
 * The popup reads this value on open to pre-fill the address input.
 */

const SELECTION_KEY = "lastSelection";

document.addEventListener("mouseup", () => {
  const selected = window.getSelection()?.toString().trim();
  if (selected) {
    chrome.storage.local.set({ [SELECTION_KEY]: selected }, () => {
      // Intentionally silent — no UI feedback at capture time.
    });
  }
});
