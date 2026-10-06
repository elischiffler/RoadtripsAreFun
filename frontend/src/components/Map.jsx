import { useEffect, useMemo, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import PropTypes from 'prop-types';

import 'mapbox-gl/dist/mapbox-gl.css';
import './Map.css';

const stopType = (type) =>
  type === 'stop' || type === 'attraction'
    ? 'Attraction'
    : (type || 'Stop').replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase());

const Map = ({ UserChatData }) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const [selectedStop, setSelectedStop] = useState(null);
  const localPin = useRef(null);
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
    // Don't reinitialise if the map already exists
    if (mapRef.current) return;
    if (localJourney) return;

    mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;
    const latitude =
      (UserChatData.startConfirmed['latitude'] + UserChatData.endConfirmed['latitude']) / 2;
    const longitude =
      (UserChatData.startConfirmed['longitude'] + UserChatData.endConfirmed['longitude']) / 2;
    const zoom_factor = Math.pow(UserChatData.route['duration'], 1 / 3.5);

    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [longitude, latitude],
      zoom: 100 / zoom_factor,
      attributionControl: false,
    });

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
              coordinates: UserChatData.route['geometry']['coordinates'],
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
            'line-color': '#C4873A', // --amber-main / --forest-main
            'line-width': 6,
            'line-opacity': 0.9,
          },
        });
      }
      const locations = [
        ...UserChatData.route.geometry.coordinates,
        ...stops.map((stop) => [stop.longitude, stop.latitude]),
      ];
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
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (localJourney || !mapRef.current || !stops.length) return;
    const map = mapRef.current;
    const popup = new mapboxgl.Popup({
      offset: 18,
      maxWidth: '240px',
      className: 'map-stop-popup',
    });
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
        for (const text of [stopType(stop.type), stop.address]) {
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
      markers.forEach((marker) => marker.remove());
    };
  }, [stops, localJourney]);

  if (localJourney) {
    const coordinates = UserChatData.route.geometry.coordinates;
    const longitudes = [
      ...coordinates.map(([longitude]) => longitude),
      ...stops.map((stop) => stop.longitude),
    ];
    const latitudes = [
      ...coordinates.map(([, latitude]) => latitude),
      ...stops.map((stop) => stop.latitude),
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
        <svg
          role="group"
          aria-label={`Local route map from ${UserChatData.startConfirmed?.address || 'start'} to ${UserChatData.endConfirmed?.address || 'destination'}`}
          viewBox="0 0 100 100"
          preserveAspectRatio="xMidYMid meet"
          className="map-container"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
        >
          <rect width="100" height="100" fill="#f8f3e9" />
          <polyline points={points} fill="none" stroke="#C4873A" strokeWidth="2" />
          <circle cx={start[0]} cy={start[1]} r="2" fill="#234a3c" />
          <circle cx={end[0]} cy={end[1]} r="2" fill="#234a3c" />
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
                <circle
                  r="4"
                  fill={stop.type === 'hotel' ? '#234a3c' : '#a56b28'}
                  stroke="#fbf8f3"
                  strokeWidth="0.7"
                />
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill="white"
                  fontSize="4"
                  fontWeight="700"
                >
                  {stop.number}
                </text>
              </g>
            );
          })}
        </svg>
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
            <p>{stopType(selectedStop.type)}</p>
            {selectedStop.address && <p>{selectedStop.address}</p>}
          </div>
        )}
      </>
    );
  }

  return (
    <div
      style={{ position: 'absolute', inset: 0 }}
      ref={mapContainerRef}
      className="map-container"
    ></div>
  );
};

Map.propTypes = {
  UserChatData: PropTypes.object.isRequired,
};

export default Map;
