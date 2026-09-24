import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import PropTypes from 'prop-types';

import 'mapbox-gl/dist/mapbox-gl.css';

const Map = ({ UserChatData }) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
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
    });

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (localJourney) {
    const coordinates = UserChatData.route.geometry.coordinates;
    const longitudes = coordinates.map(([longitude]) => longitude);
    const latitudes = coordinates.map(([, latitude]) => latitude);
    const west = Math.min(...longitudes);
    const east = Math.max(...longitudes);
    const south = Math.min(...latitudes);
    const north = Math.max(...latitudes);
    const projected = coordinates.map(([longitude, latitude]) => {
      const x = 15 + (70 * (longitude - west)) / (east - west || 1);
      const y = 85 - (70 * (latitude - south)) / (north - south || 1);
      return [x, y];
    });
    const points = projected.map(([x, y]) => `${x},${y}`).join(' ');
    const start = projected[0];
    const end = projected[projected.length - 1];
    return (
      <svg
        role="img"
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
      </svg>
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
