import { useSyncExternalStore } from 'react';
const KEY = 'roadtrips.theme';
let mode;
try {
  mode = localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light';
} catch {
  mode = 'light';
}
const listeners = new Set();
const apply = () => {
  document.documentElement.dataset.theme = mode;
  document.documentElement.style.colorScheme = mode;
};
apply();
const emit = () => {
  apply();
  listeners.forEach((fn) => fn());
};
window.addEventListener('storage', (event) => {
  if (event.key === KEY || event.key === null) {
    mode = event.newValue === 'dark' ? 'dark' : 'light';
    emit();
  }
});
export function setThemeMode(value) {
  if (!['light', 'dark'].includes(value)) return;
  mode = value;
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    /* Apply for this visit even without storage. */
  }
  emit();
}
const subscribe = (listener) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};
export function useThemeMode() {
  return useSyncExternalStore(subscribe, () => mode);
}
