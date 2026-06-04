import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import PropTypes from 'prop-types';

import 'mapbox-gl/dist/mapbox-gl.css';

const Map = ({ UserChatData }) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;
    const latitude =
      (UserChatData.startConfirmed['latitude'] + UserChatData.endConfirmed['latitude']) / 2; // central latitude
    const longitude =
      (UserChatData.startConfirmed['longitude'] + UserChatData.endConfirmed['longitude']) / 2; // central longitude
    const zoom_factor = Math.pow(UserChatData.route['duration'], 1 / 3.5); // Formula somewhat accurate

    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: 'mapbox://styles/mapbox/streets-v12',
      center: [longitude, latitude],
      zoom: 100 / zoom_factor, // As duration increases the zoom decreases
    });

    mapRef.current.on('load', () => {
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

      mapRef.current.addLayer({
        id: 'route',
        type: 'line',
        source: 'route',
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
        },
        paint: {
          'line-color': '#888',
          'line-width': 8,
        },
      });
    });
  }, [UserChatData]); // Rerender the map if UserChatData changes

  return <div style={{ height: '100%' }} ref={mapContainerRef} className="map-container"></div>;
};

Map.propTypes = {
  UserChatData: PropTypes.object.isRequired,
};

export default Map;
