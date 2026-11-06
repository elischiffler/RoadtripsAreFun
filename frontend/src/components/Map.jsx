import { useEffect, useMemo, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import PropTypes from 'prop-types';
import { validStopCoordinates } from '../services/tripPresentation';

import 'mapbox-gl/dist/mapbox-gl.css';
import './Map.css';

const NO_SUGGESTIONS = [];
const Map = ({
  UserChatData,
  suggestions = NO_SUGGESTIONS,
  selectedSuggestion = null,
  onSelectSuggestion,
}) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const [selectedStop, setSelectedStop] = useState(null);
  const [mapError, setMapError] = useState(false);
  const geometry = useMemo(
    () =>
      (UserChatData.route.geometry?.coordinates || []).filter(
        (point) => Array.isArray(point) && validStopCoordinates([point[1], point[0]])
      ),
    [UserChatData.route.geometry]
  );
  const mapToken = import.meta.env.VITE_MAPBOX_TOKEN;
  const localPin = useRef(null);
  const ideaButtons = useRef(new globalThis.Map());
  const localIdeaPin = useRef(null);
  const stopPopup = useRef(null);
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
  const localJourney = import.meta.env.VITE_LOCAL_JOURNEY === 'true';

  useEffect(() => {
    if (mapRef.current || localJourney || !mapToken || geometry.length < 2) return;
    setMapError(false);
    mapboxgl.accessToken = mapToken;
    const start = UserChatData.startConfirmed;
    const end = UserChatData.endConfirmed;
    const hasEndpoints =
      validStopCoordinates([start?.latitude, start?.longitude]) &&
      validStopCoordinates([end?.latitude, end?.longitude]);
    const center = hasEndpoints
      ? [(start.longitude + end.longitude) / 2, (start.latitude + end.latitude) / 2]
      : geometry[0];
    try {
      mapRef.current = new mapboxgl.Map({
        container: mapContainerRef.current,
        style: 'mapbox://styles/mapbox/light-v11',
        center,
        zoom: 7,
        attributionControl: false,
      });
    } catch {
      setMapError(true);
      return;
    }
    mapRef.current.on('error', () => setMapError(true));

    mapRef.current.addControl(new mapboxgl.AttributionControl({ compact: true }));

    mapRef.current.on('load', () => {
      if (!mapRef.current.getSource('route')) {
        mapRef.current.addSource('route', {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: {
              type: 'LineString',
              coordinates: geometry,
            },
          },
        });
      }

      if (!mapRef.current.getLayer('route')) {
        mapRef.current.addLayer({
          id: 'route',
          type: 'line',
          source: 'route',
          layout: {
            'line-join': 'round',
            'line-cap': 'round',
          },
          paint: {
            'line-color':
              getComputedStyle(mapContainerRef.current)
                .getPropertyValue('--rt-color-route')
                .trim() || '#175bc1',
            'line-width': 6,
            'line-opacity': 0.9,
          },
        });
      }
      const locations = [...geometry, ...stops.map((stop) => [stop.longitude, stop.latitude])];
      const bounds = [
        [Infinity, Infinity],
        [-Infinity, -Infinity],
      ];
      for (const [longitude, latitude] of locations) {
        bounds[0][0] = Math.min(bounds[0][0], longitude);
        bounds[0][1] = Math.min(bounds[0][1], latitude);
        bounds[1][0] = Math.max(bounds[1][0], longitude);
        bounds[1][1] = Math.max(bounds[1][1], latitude);
      }
      mapRef.current.fitBounds(bounds, { padding: 32, maxZoom: 12, duration: 0 });
    });

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [
    geometry,
    localJourney,
    mapToken,
    stops,
    UserChatData.startConfirmed,
    UserChatData.endConfirmed,
  ]);

  useEffect(() => {
    if (localJourney || !mapRef.current || !stops.length) return;
    const map = mapRef.current;
    const popup = new mapboxgl.Popup({
      offset: 18,
      maxWidth: '240px',
      className: 'map-stop-popup',
    });
    stopPopup.current = popup;
    let activeButton;
    popup.on('close', () => {
      if (!activeButton) return;
      activeButton.setAttribute('aria-expanded', 'false');
      if (activeButton.isConnected) activeButton.focus();
      activeButton = null;
    });
    const markers = stops.map((stop) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'map-stop-pin';
      button.dataset.type = stop.type || 'stop';
      button.textContent = String(stop.number);
      button.setAttribute('aria-label', `Stop ${stop.number}: ${stop.name}`);
      button.setAttribute('aria-expanded', 'false');
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        if (activeButton === button && popup.isOpen()) {
          popup.remove();
          return;
        }
        popup.remove();
        activeButton = button;
        const content = document.createElement('div');
        const heading = document.createElement('strong');
        heading.textContent = stop.name;
        content.append(heading);
        for (const text of [stop.address]) {
          if (!text) continue;
          const line = document.createElement('p');
          line.textContent = text;
          content.append(line);
        }
        popup.setDOMContent(content).setLngLat([stop.longitude, stop.latitude]).addTo(map);
        const element = popup.getElement();
        element.setAttribute('role', 'dialog');
        element.setAttribute('aria-label', `Stop ${stop.number}: ${stop.name}`);
        element.querySelector('.mapboxgl-popup-close-button')?.removeAttribute('aria-hidden');
        element.onkeydown = (event) => {
          if (event.key === 'Escape') {
            event.preventDefault();
            popup.remove();
          }
        };
        button.setAttribute('aria-expanded', 'true');
      });
      button.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') popup.remove();
      });
      const marker = new mapboxgl.Marker({ element: button })
        .setLngLat([stop.longitude, stop.latitude])
        .addTo(map);
      // Mapbox assigns role="img" to custom marker elements during construction.
      button.setAttribute('role', 'button');
      return marker;
    });
    return () => {
      activeButton = null;
      popup.remove();
      stopPopup.current = null;
      markers.forEach((marker) => marker.remove());
    };
  }, [stops, localJourney, geometry, mapToken]);

  useEffect(() => {
    if (localJourney || !mapRef.current) return;
    const map = mapRef.current;
    const buttons = ideaButtons.current;
    const markers = validSuggestions.map((idea) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'map-idea-pin';
      button.textContent = '+';
      button.setAttribute('aria-label', `Nearby idea: ${idea.name}`);
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => {
        stopPopup.current?.remove();
        onSelectSuggestion?.(idea);
      });
      buttons.set(idea.id, button);
      const marker = new mapboxgl.Marker({ element: button })
        .setLngLat([idea.coordinates[1], idea.coordinates[0]])
        .addTo(map);
      button.setAttribute('role', 'button');
      return marker;
    });
    return () => {
      buttons.clear();
      markers.forEach((marker) => marker.remove());
    };
  }, [validSuggestions, localJourney, geometry, mapToken, stops, onSelectSuggestion]);

  useEffect(() => {
    for (const [id, button] of ideaButtons.current) {
      button.setAttribute('aria-pressed', String(id === selectedSuggestion?.id));
    }
    if (
      !localJourney &&
      selectedSuggestion &&
      validStopCoordinates(selectedSuggestion.coordinates)
    ) {
      mapRef.current?.easeTo?.({
        center: [selectedSuggestion.coordinates[1], selectedSuggestion.coordinates[0]],
        zoom: 12,
        duration: 0,
      });
    }
  }, [selectedSuggestion, localJourney, validSuggestions, geometry, stops]);

  const closeIdea = () => {
    onSelectSuggestion?.(null);
    (localJourney
      ? localIdeaPin.current
      : ideaButtons.current.get(selectedSuggestion?.id)
    )?.focus();
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
  if (!localJourney && !mapToken)
    return (
      <p className="map-unavailable" role="status">
        The map is unavailable because its access token is not configured. Your itinerary is still
        available.
      </p>
    );

  if (localJourney) {
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
        <p className="map-fixture-label">Local fixture · route schematic</p>
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
  }

  return (
    <>
      <div
        style={{ position: 'absolute', inset: 0 }}
        ref={mapContainerRef}
        className="map-container"
      ></div>
      {ideaDetail}
      {mapError && (
        <p className="map-unavailable map-error" role="status">
          The map could not be loaded. Your itinerary is still available. Refresh to retry the map.
        </p>
      )}
    </>
  );
};

Map.propTypes = {
  UserChatData: PropTypes.object.isRequired,
  suggestions: PropTypes.arrayOf(PropTypes.object),
  selectedSuggestion: PropTypes.object,
  onSelectSuggestion: PropTypes.func,
};

export default Map;
