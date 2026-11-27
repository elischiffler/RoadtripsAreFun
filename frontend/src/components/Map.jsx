import LegacyDirectionsCredit from './LegacyDirectionsCredit';
import { useMemo, useRef, useState } from 'react';
import AppleRouteViewer from './AppleRouteViewer';
import { isAppleRoute } from '../services/directionsCapability';
import { appleMapsConfigured } from '../services/appleMaps';
import PropTypes from 'prop-types';
import { validStopCoordinates } from '../services/tripPresentation';

import './Map.css';

const NO_SUGGESTIONS = [];
const LegacyRouteMap = ({
  UserChatData,
  suggestions = NO_SUGGESTIONS,
  selectedSuggestion = null,
  onSelectSuggestion,
}) => {
  const [selectedStop, setSelectedStop] = useState(null);
  const geometry = useMemo(
    () =>
      (UserChatData.route.geometry?.coordinates || []).filter(
        (point) => Array.isArray(point) && validStopCoordinates([point[1], point[0]])
      ),
    [UserChatData.route.geometry]
  );
  const localPin = useRef(null);
  const localIdeaPin = useRef(null);
  const validSuggestions = useMemo(
    () => suggestions.filter((idea) => idea && validStopCoordinates(idea.coordinates)),
    [suggestions]
  );
  const stops = useMemo(
    () =>
      (UserChatData.route.stops || []).flatMap((stop, index) => {
        const coordinates = stop?.coordinates;
        if (
          !Array.isArray(coordinates) ||
          coordinates.length !== 2 ||
          !coordinates.every((value) => typeof value === 'number' && Number.isFinite(value)) ||
          Math.abs(coordinates[0]) > 90 ||
          Math.abs(coordinates[1]) > 180
        )
          return [];
        return [
          {
            ...stop,
            number: index + 1,
            name: stop.name || `Stop ${index + 1}`,
            longitude: coordinates[1],
            latitude: coordinates[0],
          },
        ];
      }),
    [UserChatData.route.stops]
  );
  const closeIdea = () => {
    onSelectSuggestion?.(null);
    localIdeaPin.current?.focus();
  };
  const ideaDetail = selectedSuggestion && (
    <div
      className="map-idea-detail"
      role="region"
      aria-label="Selected nearby idea"
      aria-live="polite"
      onKeyDown={(event) => {
        if (event.key === 'Escape') closeIdea();
      }}
    >
      <button
        type="button"
        className="map-stop-close"
        aria-label="Close nearby idea"
        onClick={closeIdea}
      >
        ×
      </button>
      <strong>{selectedSuggestion.name}</strong>
      <p>Unscheduled idea · opening hours, availability and detour timing need checking.</p>
      <p>
        Source:{' '}
        {selectedSuggestion.source_attribution || selectedSuggestion.source || 'Place catalog'}
      </p>
    </div>
  );

  if (geometry.length < 2)
    return (
      <p className="map-unavailable" role="status">
        A route map is not available for this saved trip.
      </p>
    );
  const coordinates = geometry;
  const longitudes = [
    ...coordinates.map(([longitude]) => longitude),
    ...stops.map((stop) => stop.longitude),
    ...validSuggestions.map((idea) => idea.coordinates[1]),
  ];
  const latitudes = [
    ...coordinates.map(([, latitude]) => latitude),
    ...stops.map((stop) => stop.latitude),
    ...validSuggestions.map((idea) => idea.coordinates[0]),
  ];
  const west = Math.min(...longitudes);
  const east = Math.max(...longitudes);
  const south = Math.min(...latitudes);
  const north = Math.max(...latitudes);
  const project = ([longitude, latitude]) => {
    const x = 15 + (70 * (longitude - west)) / (east - west || 1);
    const y = 85 - (70 * (latitude - south)) / (north - south || 1);
    return [x, y];
  };
  const projected = coordinates.map(project);
  const points = projected.map(([x, y]) => `${x},${y}`).join(' ');
  const start = projected[0];
  const end = projected[projected.length - 1];
  return (
    <>
      <p className="map-fixture-label">
        {import.meta.env.VITE_LOCAL_JOURNEY === 'true'
          ? 'Local fixture · route schematic'
          : 'Saved route schematic'}
      </p>
      {import.meta.env.VITE_LOCAL_JOURNEY !== 'true' && <LegacyDirectionsCredit />}
      <svg
        role="group"
        aria-label={`Local route map from ${UserChatData.startConfirmed?.address || 'start'} to ${UserChatData.endConfirmed?.address || 'destination'}`}
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid meet"
        className="map-container"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <rect width="100" height="100" fill="var(--rt-color-page, #f4f6f3)" />
        <polyline
          points={points}
          fill="none"
          stroke="var(--rt-color-route, #175bc1)"
          strokeWidth="2"
        />
        <circle cx={start[0]} cy={start[1]} r="2" fill="var(--rt-color-accent, #165b50)" />
        <circle cx={end[0]} cy={end[1]} r="2" fill="var(--rt-color-accent, #165b50)" />
        {stops.map((stop) => {
          const [x, y] = project([stop.longitude, stop.latitude]);
          return (
            <g
              key={stop.number}
              className="map-stop-svg-pin"
              role="button"
              tabIndex={0}
              aria-label={`Stop ${stop.number}: ${stop.name}`}
              aria-expanded={selectedStop?.number === stop.number}
              transform={`translate(${x}, ${y})`}
              onClick={(event) => {
                localPin.current = event.currentTarget;
                setSelectedStop((current) => (current?.number === stop.number ? null : stop));
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  localPin.current = event.currentTarget;
                  setSelectedStop((current) => (current?.number === stop.number ? null : stop));
                } else if (event.key === 'Escape') setSelectedStop(null);
              }}
            >
              <circle r="8" fill="transparent" />
              <circle
                r="4"
                fill={
                  stop.type === 'hotel'
                    ? 'var(--rt-color-accent, #165b50)'
                    : 'var(--rt-color-route, #175bc1)'
                }
                stroke="var(--rt-color-surface, white)"
                strokeWidth="0.7"
              />
              <text
                textAnchor="middle"
                dominantBaseline="central"
                fill="var(--rt-color-on-accent, white)"
                fontSize="4"
                fontWeight="700"
              >
                {stop.number}
              </text>
            </g>
          );
        })}
        {validSuggestions.map((idea) => {
          const [x, y] = project([idea.coordinates[1], idea.coordinates[0]]);
          return (
            <g
              key={idea.id}
              className="map-idea-svg-pin"
              role="button"
              tabIndex={0}
              aria-label={`Nearby idea: ${idea.name}`}
              aria-pressed={selectedSuggestion?.id === idea.id}
              transform={`translate(${x}, ${y})`}
              onClick={(event) => {
                localIdeaPin.current = event.currentTarget;
                setSelectedStop(null);
                onSelectSuggestion?.(idea);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  localIdeaPin.current = event.currentTarget;
                  setSelectedStop(null);
                  onSelectSuggestion?.(idea);
                }
              }}
            >
              <circle r="8" fill="transparent" />
              <circle
                r="4"
                fill="var(--rt-color-surface, white)"
                stroke="var(--rt-color-route, #175bc1)"
                strokeWidth={selectedSuggestion?.id === idea.id ? 1.2 : 0.7}
              />
              <text
                textAnchor="middle"
                dominantBaseline="central"
                fill="var(--rt-color-route, #175bc1)"
                fontSize="5"
              >
                +
              </text>
            </g>
          );
        })}
      </svg>
      {ideaDetail}
      {selectedStop && (
        <div
          className="map-stop-local-popup"
          role="dialog"
          aria-label={`Stop ${selectedStop.number}`}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              setSelectedStop(null);
              localPin.current?.focus();
            }
          }}
        >
          <button
            type="button"
            className="map-stop-close"
            aria-label="Close location"
            onClick={() => {
              setSelectedStop(null);
              localPin.current?.focus();
            }}
          >
            ×
          </button>
          <strong>{selectedStop.name}</strong>
          {selectedStop.address && <p>{selectedStop.address}</p>}
        </div>
      )}
    </>
  );
};

const Map = (props) =>
  isAppleRoute(props.UserChatData?.route) || appleMapsConfigured() ? (
    <AppleRouteViewer
      route={props.UserChatData.route}
      suggestions={props.suggestions ?? NO_SUGGESTIONS}
      selectedSuggestion={props.selectedSuggestion}
      onSelectSuggestion={props.onSelectSuggestion}
      studio={props.studio}
    />
  ) : (
    <LegacyRouteMap {...props} />
  );

Map.propTypes = {
  UserChatData: PropTypes.object.isRequired,
  suggestions: PropTypes.arrayOf(PropTypes.object),
  selectedSuggestion: PropTypes.object,
  onSelectSuggestion: PropTypes.func,
  studio: PropTypes.bool,
};

LegacyRouteMap.propTypes = Map.propTypes;

export default Map;
