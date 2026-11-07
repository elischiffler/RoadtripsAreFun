import { arrivalEvent, createArrivalDetector } from './tripArrivals';

/** Owns one opt-in browser watch; callers must stop it on trip/view teardown. */
export function startForegroundArrivals({
  tripId,
  targets,
  onArrival,
  onStatus,
  excludedIds,
  canRecord,
  isCurrent,
}) {
  const detector = createArrivalDetector(targets);
  let watchId = null;
  let generation = 0;
  let stopped = false;
  let freshnessTimer;
  const clearWatch = () => {
    generation += 1;
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    watchId = null;
    clearTimeout(freshnessTimer);
    detector.reset();
  };
  const stop = () => {
    stopped = true;
    clearWatch();
    document.removeEventListener('visibilitychange', visibility);
    window.removeEventListener('pagehide', pageHidden);
    window.removeEventListener('auth-changed', accountChanged);
  };
  const pageHidden = () => {
    stop();
    onStatus({ status: 'ended' });
  };
  const accountChanged = () => {
    if (!isCurrent()) {
      stop();
      onStatus({ status: 'signed-out' });
    }
  };
  const watch = () => {
    if (stopped || !isCurrent()) return;
    if (document.visibilityState === 'hidden') {
      onStatus({ status: 'paused' });
      return;
    }
    const current = ++generation;
    onStatus({ status: 'waiting' });
    try {
      watchId = navigator.geolocation.watchPosition(
        (position) => {
          if (stopped || generation !== current || document.visibilityState === 'hidden') return;
          if (!isCurrent()) return accountChanged();
          clearTimeout(freshnessTimer);
          freshnessTimer = setTimeout(() => {
            onStatus({ status: 'waiting' });
          }, 10000);
          if (!canRecord()) {
            detector.reset();
            onStatus({ status: 'saving' });
            return;
          }
          const result = detector.sample(
            {
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              accuracy: position.coords.accuracy,
              speed: position.coords.speed,
              timestamp: position.timestamp,
            },
            Date.now(),
            excludedIds()
          );
          onStatus(result);
          if (result.arrival) onArrival(arrivalEvent(tripId, result.arrival));
        },
        (error) => {
          if (stopped || generation !== current) return;
          clearTimeout(freshnessTimer);
          detector.reset();
          onStatus({ status: error.code === 1 ? 'denied' : 'unavailable' });
          stop();
        },
        { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
      );
    } catch {
      stop();
      onStatus({ status: 'unavailable' });
    }
  };
  const visibility = () => {
    clearWatch();
    watch();
  };
  document.addEventListener('visibilitychange', visibility);
  window.addEventListener('pagehide', pageHidden);
  window.addEventListener('auth-changed', accountChanged);
  watch();
  return stop;
}
