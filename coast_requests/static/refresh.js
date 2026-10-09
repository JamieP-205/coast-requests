// New requests arrive during a show, so check for changes every 20 seconds.
// The page only reloads when something has changed, and not while Jim has a
// "More" menu open, so it never jumps under his finger.

const board = document.querySelector('[data-version]');
const CHECK_EVERY_MS = 20000;

async function checkForChanges() {
  if (document.querySelector('details[open]')) return;
  try {
    const response = await fetch('/updates', { cache: 'no-store' });
    if (!response.ok) return;
    const { version } = await response.json();
    if (version !== board.dataset.version) location.reload();
  } catch {
    // Offline for a moment, or signed out: try again next time.
  }
}

setInterval(checkForChanges, CHECK_EVERY_MS);
