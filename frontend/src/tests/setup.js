import '@testing-library/jest-dom';

// ── Silence app console output during tests ──────────────────────────────────
// The app uses console.debug/warn/error for DB logs, auth errors, and router
// warnings. These are expected in tests (we intentionally trigger error paths)
// and just add noise. Vitest will still show its own failure output clearly.
beforeEach(() => {
  vi.spyOn(console, 'log').mockImplementation(() => {});
  vi.spyOn(console, 'debug').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Browser API stubs ────────────────────────────────────────────────────────

// mapbox-gl is not runnable in jsdom — stub the whole module
vi.mock('mapbox-gl', () => ({
  default: {
    Map: vi.fn(() => ({
      on: vi.fn(),
      remove: vi.fn(),
      addControl: vi.fn(),
      getSource: vi.fn(),
      addSource: vi.fn(),
      addLayer: vi.fn(),
      setStyle: vi.fn(),
      fitBounds: vi.fn(),
      resize: vi.fn(),
    })),
    NavigationControl: vi.fn(),
    Marker: vi.fn(() => ({ setLngLat: vi.fn().mockReturnThis(), addTo: vi.fn().mockReturnThis() })),
    Popup: vi.fn(() => ({
      setLngLat: vi.fn().mockReturnThis(),
      setHTML: vi.fn().mockReturnThis(),
      addTo: vi.fn().mockReturnThis(),
    })),
    supported: vi.fn(() => true),
  },
}));

// ldrs web-components crash in jsdom — stub the register call
vi.mock('ldrs', () => ({
  ring: { register: vi.fn() },
  waveform: { register: vi.fn() },
}));

// Stub navigator.geolocation for LocationInput tests
Object.defineProperty(global.navigator, 'geolocation', {
  writable: true,
  value: {
    getCurrentPosition: vi.fn(),
  },
});

// Stub window.matchMedia (MUI uses it)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Stub scrollIntoView (used by chat auto-scroll)
Element.prototype.scrollIntoView = vi.fn();
