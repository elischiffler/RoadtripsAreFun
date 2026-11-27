import LegacyDirectionsCredit from './LegacyDirectionsCredit';
import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { appleMapsConfigured, loadAppleMaps } from '../services/appleMaps';
import request from '../services/protectedRequest';
import { getSession, isCurrentSession } from '../services/session';
import { getStudioSession, studioRequest } from '../services/studioSession';
import { isAppleRoute } from '../services/directionsCapability';
import { validStopCoordinates } from '../services/tripPresentation';

const isRoadPoint = (point) => Array.isArray(point) && validStopCoordinates([point[1], point[0]]);
const line = (route) => {
  const points = route?.geometry?.coordinates;
  return Array.isArray(points) && points.length >= 2 && points.every(isRoadPoint) ? points : null;
};

export default function AppleRouteViewer({
  route,
  suggestions,
  selectedSuggestion,
  onSelectSuggestion,
  studio = false,
}) {
  const host = useRef(null);
  const mountedMap = useRef(null);
  const latest = useRef(onSelectSuggestion);
  latest.current = onSelectSuggestion;
  const [rendered, setRendered] = useState(null);
  const [attempt, retry] = useState(0);
  const [selectedStop, selectStop] = useState(null);
  const active = appleMapsConfigured();
  const apple = isAppleRoute(route);

  useEffect(() => {
    if (!host.current || !active) return;
    const controller = new AbortController();
    const session = getSession();
    const studioToken = studio ? getStudioSession()?.token : null;
    const current = () =>
      !controller.signal.aborted &&
      isCurrentSession(session) &&
      (!studio || studioToken === getStudioSession()?.token);
    let map;
    let sdk;
    const unavailable = () => {
      if (current()) setRendered({ route, attempt, failed: true });
    };
    const start = async () => {
      try {
        const points = line(route);
        const coordinates = points
          ? points
          : await (async () => {
              if (
                !apple ||
                !Array.isArray(route.coordinates) ||
                route.coordinates.length < 2 ||
                route.coordinates.length > 25 ||
                !route.coordinates.every(validStopCoordinates)
              )
                throw new Error('Saved route waypoints are unavailable.');
              const payload = { coordinates: route.coordinates };
              const { data } = studio
                ? await studioRequest('post', 'route-directions', payload, controller.signal)
                : await request.post(
                    import.meta.env.VITE_BACKEND_SERVER + 'route-directions',
                    payload,
                    { signal: controller.signal, timeout: 20000 }
                  );
              if (!isAppleRoute(data) || !line(data))
                throw new Error('Apple directions unavailable.');
              return line(data);
            })();
        if (!current()) return;
        sdk = await loadAppleMaps();
        if (!current()) return;
        sdk.addEventListener('error', unavailable);
        map = new sdk.Map(host.current, { showsMapTypeControl: false });
        mountedMap.current = map;
        const geometry = coordinates.map(([lon, lat]) => new sdk.Coordinate(lat, lon));
        const path = new sdk.PolylineOverlay(geometry, {
          style: new sdk.Style({
            lineWidth: 5,
            strokeColor: '#165b50',
            lineJoin: 'round',
            lineCap: 'round',
          }),
        });
        map.addItems([path]);
        map.showItems([path], { animate: false, padding: new sdk.Padding(32, 32, 32, 32) });
        setRendered({ route, attempt, sdk, map });
      } catch {
        unavailable();
      }
    };
    void start();
    return () => {
      controller.abort();
      sdk?.removeEventListener('error', unavailable);
      mountedMap.current = null;
      map?.destroy();
    };
  }, [active, apple, route, attempt, studio]);

  const state = rendered?.route === route && rendered.attempt === attempt ? rendered : null;
  useEffect(() => {
    if (!state?.map) return;
    const { map, sdk } = state;
    const markers = [
      ...(route.stops || []).map((stop, index) => ({ place: stop, number: index + 1 })),
      ...suggestions.map((place) => ({ place })),
    ].flatMap(({ place, number }) => {
      if (!validStopCoordinates(place?.coordinates)) return [];
      const button = document.createElement('button');
      button.type = 'button';
      button.className = number ? 'map-stop-pin' : 'map-idea-pin';
      button.textContent = number ? String(number) : '+';
      if (number) button.dataset.type = place.type ?? 'stop';
      button.setAttribute(
        'aria-label',
        number ? 'Stop ' + number + ': ' + place.name : 'Nearby idea: ' + place.name
      );
      const pressed = number ? place === selectedStop : place === selectedSuggestion;
      button.setAttribute('aria-pressed', String(pressed));
      button.onclick = (event) => {
        event.stopPropagation();
        if (number) {
          latest.current?.(null);
          selectStop(pressed ? null : place);
        } else {
          selectStop(null);
          latest.current?.(pressed ? null : place);
        }
      };
      return new sdk.Annotation(new sdk.Coordinate(...place.coordinates), () => button, {
        title: place.name,
        calloutEnabled: false,
        animates: false,
      });
    });
    map.addItems(markers);
    return () => {
      if (mountedMap.current === map) map.removeItems(markers);
    };
  }, [state, route.stops, suggestions, selectedSuggestion, selectedStop]);

  return (
    <>
      <div className="map-container apple-route-viewer" ref={host} aria-label="Apple Maps route" />
      {state?.map && !apple && <LegacyDirectionsCredit />}
      {(!active || state?.failed) && (
        <div className="map-unavailable">
          <p role="status">
            Apple Maps directions are unavailable. Your itinerary is still available.
          </p>
          {active && (
            <button type="button" onClick={() => retry((value) => value + 1)}>
              Retry directions
            </button>
          )}
        </div>
      )}
      {active && !state && (
        <p role="status" className="map-unavailable">
          Loading Apple Maps…
        </p>
      )}
      {state?.map && (selectedStop || selectedSuggestion) && (
        <div className="map-idea-detail" role="status">
          <strong>{(selectedStop || selectedSuggestion).name}</strong>
          {!selectedStop && (
            <p>Unscheduled idea · opening hours, availability and detour timing need checking.</p>
          )}
          <p>
            Source:{' '}
            {(selectedStop || selectedSuggestion).source_attribution ||
              (selectedStop || selectedSuggestion).source ||
              'Place catalog'}
          </p>
          {(selectedStop || selectedSuggestion).address && (
            <p>{(selectedStop || selectedSuggestion).address}</p>
          )}
        </div>
      )}
    </>
  );
}

AppleRouteViewer.propTypes = {
  route: PropTypes.object.isRequired,
  suggestions: PropTypes.array.isRequired,
  selectedSuggestion: PropTypes.object,
  onSelectSuggestion: PropTypes.func,
  studio: PropTypes.bool,
};
