import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import PropTypes from 'prop-types';

import 'mapbox-gl/dist/mapbox-gl.css';

const Map = ({ UserChatData }) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    // Don't reinitialise if the map already exists
    if (mapRef.current) return;

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
