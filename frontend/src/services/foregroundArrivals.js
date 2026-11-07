import { arrivalEvent, createArrivalDetector } from './tripArrivals';

/** One opt-in foreground watch. A hidden page must be explicitly enabled again. */
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
  let watchId = null,
    generation = 0,
    stopped = false,
    freshnessTimer;
  const clearWatch = () => {
    generation++;
    if (watchId !== null) navigator.geolocation?.clearWatch?.(watchId);
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
  const end = (status) => {
    stop();
    onStatus({ status });
  };
  const pageHidden = () => end('ended');
  const visibility = () => {
    if (document.visibilityState !== 'visible') end('paused');
  };
  const accountChanged = () => {
    if (!isCurrent()) end('signed-out');
  };
  document.addEventListener('visibilitychange', visibility);
  window.addEventListener('pagehide', pageHidden);
  window.addEventListener('auth-changed', accountChanged);
  if (!isCurrent()) {
    end('signed-out');
    return stop;
  }
  if (document.visibilityState !== 'visible') {
    end('paused');
    return stop;
  }
  const current = ++generation;
  onStatus({ status: 'waiting' });
  try {
    const id = navigator.geolocation.watchPosition(
      (position) => {
        if (stopped || generation !== current) return;
        if (document.visibilityState !== 'visible') return end('paused');
        if (!isCurrent()) return end('signed-out');
        clearTimeout(freshnessTimer);
        freshnessTimer = setTimeout(() => {
          if (stopped || generation !== current) return;
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
        if (result.arrival && onArrival(arrivalEvent(tripId, result.arrival)) === false)
          end('ended');
        if (result.status === 'done') end('done');
      },
      (error) => {
        if (!stopped && generation === current) end(error.code === 1 ? 'denied' : 'unavailable');
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
    );
    if (!stopped && generation === current) watchId = id;
    else navigator.geolocation.clearWatch(id);
  } catch {
    end('unavailable');
  }
  return stop;
}
