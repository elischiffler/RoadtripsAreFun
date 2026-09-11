import axios from 'axios';
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
    });
    const route = response.data;
    return route;
  } catch (error) {
    // Log any errors encountered during the request
    console.error('Error creating initial route:', error);
    return null;
  }
};
// Dev-mode: which routing algorithm to request. Stored in localStorage by the
// settings popup (see AlgorithmSettings.jsx). When unset, the backend uses its
// default, so production behavior is unchanged.
export const ROUTING_ALGORITHM_KEY = 'devRoutingAlgorithm';

export const getRoutingAlgorithm = () => {
  try {
    return localStorage.getItem(ROUTING_ALGORITHM_KEY) || null;
  } catch {
    return null;
  }
};

export const getFinalRoute = async (initial_route, budget, stops) => {
  try {
    const data = {
      initial_route: initial_route,
      num_stops: stops,
      budget: budget,
    };

    // Dev-mode algorithm override: only sent when explicitly chosen.
    const algorithm = getRoutingAlgorithm();
    if (algorithm) {
      data.algorithm = algorithm;
    }

    // Send request for a route given the user inputs
    const response = await axios.post(
      `${import.meta.env.VITE_BACKEND_SERVER}generate-final-route`,
      data
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
