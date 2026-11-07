import PlaceContext from '../../components/PlaceContext';
import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { validStopCoordinates } from '../../services/tripPresentation';
import './OnboardingMap.css';

const validLine = (line) =>
  Array.isArray(line) &&
  line.length >= 2 &&
  line.length <= 10000 &&
  line.every((point) => Array.isArray(point) && validStopCoordinates([point[1], point[0]]));

function plot(line, markers, size) {
  const anchor = line[0]?.[0] ?? markers[0]?.point[0] ?? 0;
  const project = ([longitude, latitude]) => {
    let lon = longitude;
    while (lon - anchor > 180) lon -= 360;
    while (lon - anchor < -180) lon += 360;
    const lat = (Math.max(-85, Math.min(85, latitude)) * Math.PI) / 180;
    return [(lon * Math.PI) / 180, Math.log(Math.tan(Math.PI / 4 + lat / 2))];
  };
  const points = [...line, ...markers.map((marker) => marker.point)].map(project);
  if (!points.length) return { path: '', markers: [] };
  const xs = points.map(([x]) => x),
    ys = points.map(([, y]) => y);
  const minimumX = Math.min(...xs),
    maximumX = Math.max(...xs);
  const minimumY = Math.min(...ys),
    maximumY = Math.max(...ys);
  const width = Math.max(maximumX - minimumX, 0.002),
    height = Math.max(maximumY - minimumY, 0.002);
  // Reserve the actual native button area, including when text grows or the
  // persistent preview becomes compact. Source positions never become fake pins.
  const availableWidth = Math.max(
    0,
    Math.min(272, 360 * (1 - (size.target + size.gap * 2) / size.width))
  );
  const availableHeight = Math.max(
    0,
    Math.min(104, 160 * (1 - (size.target + size.gap * 2) / size.height))
  );
  const scale = Math.min(availableWidth / width, availableHeight / height);
  const centerX = (minimumX + maximumX) / 2,
    centerY = (minimumY + maximumY) / 2;
  const position = (point) => {
    const [x, y] = project(point);
    return [180 + (x - centerX) * scale, 80 - (y - centerY) * scale];
  };
  return {
    path: line.map((point, index) => `${index ? 'L' : 'M'}${position(point).join(',')}`).join(' '),
    markers: markers.map((marker) => ({ ...marker, position: position(marker.point) })),
  };
}

const endpoint = (place, kind, letter) =>
  place && validStopCoordinates([place.latitude, place.longitude])
    ? {
        id: kind,
        point: [place.longitude, place.latitude],
        label: place.address,
        kind,
        symbol: letter,
        confirmed: place.confirmed === true,
      }
    : null;

export default function OnboardingMap({
  origin,
  destination,
  route,
  ideas = [],
  stayAreas = [],
  phase = 'draft',
  stage = 0,
}) {
  const [selection, setSelection] = useState(null);
  const canvas = useRef(null);
  const [size, setSize] = useState({ width: 360, height: 160, target: 44, gap: 0 });
  const line = validLine(route?.geometry?.coordinates) ? route.geometry.coordinates : [];
  const realStops = (Array.isArray(route?.stops) ? route.stops : []).filter(
    (stop) => ['stop', 'hotel'].includes(stop?.type) && validStopCoordinates(stop.coordinates)
  );
  const markers = [
    endpoint(origin, 'origin', 'A'),
    endpoint(destination, 'destination', 'B'),
    ...realStops.map((stop, index) => ({
      id: stop.provider_id || `stop:${index}`,
      point: [stop.coordinates[1], stop.coordinates[0]],
      label: stop.name,
      kind: stop.type === 'hotel' ? 'hotel' : 'stop',
      symbol: stop.type === 'hotel' ? 'H' : String(index + 1),
      context: route?.place_context?.[stop.provider_id] ?? stop.place_context,
    })),
    ...(realStops.length
      ? []
      : ideas
          .slice(0, 4)
          .filter((place) => validStopCoordinates(place.coordinates))
          .map((place) => ({
            id: place.id,
            point: [place.coordinates[1], place.coordinates[0]],
            label: place.name,
            kind: 'idea',
            symbol: '·',
            context: place.place_context,
          }))),
    ...stayAreas
      .filter((area) => validStopCoordinates(area.coordinates))
      .map((area, index) => ({
        id: `area:${index}`,
        point: [area.coordinates[1], area.coordinates[0]],
        label: area.label || 'Possible rest region',
        kind: 'area',
        symbol: '◌',
      })),
  ].filter(Boolean);
  useEffect(() => {
    if (!canvas.current || typeof ResizeObserver === 'undefined') return;
    const element = canvas.current;
    const observer = new ResizeObserver(() => {
      const bounds = element.getBoundingClientRect();
      const pin = element.querySelector('button');
      const target = pin?.getBoundingClientRect().width ?? 44;
      const gap = Number.parseFloat(getComputedStyle(element.parentElement).rowGap) || 0;
      if (bounds.width > 0 && bounds.height > 0)
        setSize((old) =>
          old.width === bounds.width &&
          old.height === bounds.height &&
          old.target === target &&
          old.gap === gap
            ? old
            : { width: bounds.width, height: bounds.height, target, gap }
        );
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [markers.length]);
  const projected = plot(line, markers, size);
  const selected = markers.find((marker) => marker.id === selection);
  const state =
    { draft: 'Draft', checking: 'Checking', candidate: 'Trip option', confirmed: 'Checked route' }[
      phase
    ] || 'Draft';
  return (
    <section className="setup-map" aria-label="Trip preview" data-phase={phase} data-stage={stage}>
      <header className="setup-map-heading">
        <h3 className="rt-copy">Your route</h3>
        <span className="rt-caption">{state}</span>
      </header>
      <div ref={canvas} className="setup-map-canvas">
        <svg
          viewBox="0 0 360 160"
          preserveAspectRatio="none"
          role="img"
          aria-label={
            line.length ? `${state} route geometry` : 'Locations preview; no road route yet'
          }
        >
          <path
            className="setup-map-grid"
            d="M0 40H360 M0 80H360 M0 120H360 M90 0V160 M180 0V160 M270 0V160"
          />
          {projected.path && <path className="setup-map-route" d={projected.path} />}
        </svg>
        {projected.markers.map((marker) => (
          <button
            key={marker.id}
            type="button"
            className="setup-map-pin"
            data-kind={marker.kind}
            data-confirmed={marker.confirmed}
            style={{ left: `${marker.position[0] / 3.6}%`, top: `${marker.position[1] / 1.6}%` }}
            onClick={() => setSelection(selection === marker.id ? null : marker.id)}
            aria-expanded={selection === marker.id}
            aria-label={`${marker.kind === 'idea' ? 'Unscheduled idea' : marker.kind === 'area' ? 'Approximate rest region' : marker.kind === 'hotel' ? 'Hotel option' : marker.confirmed ? 'Confirmed location' : 'Draft location'}: ${marker.label}`}
          >
            <span aria-hidden="true">{marker.symbol}</span>
          </button>
        ))}
        {!markers.length && (
          <p className="setup-map-empty rt-caption">Add your start and destination.</p>
        )}
      </div>
      <div className="setup-map-endpoints rt-caption">
        <span>
          A · {origin?.address || 'Start'}
          {origin?.confirmed ? '' : ' · unconfirmed'}
        </span>
        <span>
          B · {destination?.address || 'Destination'}
          {destination?.confirmed ? '' : ' · unconfirmed'}
        </span>
      </div>
      {selected && (
        <div className="rt-caption" role="status">
          {selected.label}
          <PlaceContext context={selected.context} />
          {selected.kind === 'idea'
            ? ' · not scheduled'
            : selected.kind === 'area'
              ? ' · estimated area, not a hotel or availability check'
              : selected.kind === 'hotel'
                ? ' · not booked'
                : ''}
        </div>
      )}
      {!selected && (ideas.length > 0 || stayAreas.length > 0) && (
        <p className="rt-caption">
          {ideas.length ? 'Catalog ideas, not scheduled stops.' : ''}
          {stayAreas.length ? ' Rest regions are approximate; no hotels checked.' : ''}
        </p>
      )}
    </section>
  );
}
OnboardingMap.propTypes = {
  origin: PropTypes.object,
  destination: PropTypes.object,
  route: PropTypes.object,
  ideas: PropTypes.array,
  stayAreas: PropTypes.array,
  phase: PropTypes.string,
  stage: PropTypes.number,
};
