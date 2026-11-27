let pending;

function token() {
  if (import.meta.env.VITE_LOCAL_JOURNEY === 'true') return '';
  return import.meta.env.VITE_APPLE_MAPS_TOKEN?.trim();
}

export function appleMapsConfigured() {
  return Boolean(token());
}

async function initialize(publicToken) {
  const { load } = await import('@apple/mapkit-loader');
  const events = new AbortController();
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('Apple Maps timed out.')), 15000);
  });
  try {
    const sdk = await Promise.race([load({ version: '6' }), timeout]);
    const configured = new Promise((resolve, reject) => {
      // Subscribe before authorizing so a rejected origin/token cannot yield a blank successful map.
      sdk.addEventListener('configuration-change', resolve, { once: true, signal: events.signal });
      sdk.addEventListener('error', () => reject(new Error('Apple Maps authorization failed.')), {
        once: true,
        signal: events.signal,
      });
      sdk.init({ authorizationCallback: (done) => done(publicToken) });
    });
    await Promise.race([configured, timeout]);
    await Promise.race([sdk.load(['full-map']), timeout]);
    return sdk;
  } finally {
    events.abort();
    clearTimeout(timer);
  }
}

export function loadAppleMaps() {
  const publicToken = token();
  if (!publicToken) return Promise.reject(new Error('Apple Maps is not configured.'));
  if (!pending) {
    pending = initialize(publicToken).catch((error) => {
      // A failed core script has already emitted its load/error event.
      if (!window.mapkit) {
        document.head
          .querySelector('script[src="https://cdn.apple-mapkit.com/mk/6/mapkit.core.js"]')
          ?.remove();
      }
      pending = undefined;
      throw error;
    });
  }
  return pending;
}
