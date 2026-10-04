import axios from 'axios';
import { backendAuthConfig } from '../../services/backendAuth';
import { getRoutingAlgorithm } from '../../services/routingSettings';
export { getRoutingAlgorithm, ROUTING_ALGORITHM_KEY } from '../../services/routingSettings';
export const getInitialRoute = async (start_lat, start_lon, end_lat, end_lon) => {
  try {
    const params = {
      start_lat: start_lat,
      start_lon: start_lon,
      end_lat: end_lat,
      end_lon: end_lon,
    };
    const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}get-initial-route`, {
      params: params,
      ...backendAuthConfig(),
    });
    const route = response.data;
    return route;
  } catch (error) {
    // Log any errors encountered during the request
    console.error('Error creating initial route:', error);
    return null;
  }
};
export const getFinalRoute = async (
  initial_route,
  budget,
  stops,
  personaWeights = null,
  start = null,
  travelerCount = null,
  hotelRooms = null
) => {
  try {
    const data = {
      initial_route: initial_route,
      num_stops: stops,
      budget: budget,
      traveler_count: travelerCount,
      hotel_rooms: hotelRooms,
    };

    // Dev-mode algorithm override: only sent when explicitly chosen.
    const algorithm = getRoutingAlgorithm();
    if (algorithm) {
      data.algorithm = algorithm;
    }
    if (personaWeights) data.persona_weights = personaWeights;
    if (start) data.start = start;

    // Send request for a route given the user inputs
    const response = await axios.post(
      `${import.meta.env.VITE_BACKEND_SERVER}generate-final-route`,
      data,
      backendAuthConfig()
    );

    // Access route information returned
    const route = response.data;

    // Return route structure
    return route;
  } catch (error) {
    // Log any errors encountered during the request
    console.error('Error creating final route:', error);
    return null;
  }
};
