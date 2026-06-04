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
    console.log('Initial route', route);
    return route;
  } catch (error) {
    // Log any errors encountered during the request
    console.error('Error creating initial route:', error);
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

    // Send request for a route given the user inputs
    const response = await axios.post(
      `${import.meta.env.VITE_BACKEND_SERVER}generate-final-route`,
      data
    );

    // Access route information returned
    const route = response.data;

    // Return route structure
    console.log('Specified route:', route);
    return route;
  } catch (error) {
    // Log any errors encountered during the request
    console.error('Error creating final route:', error);
    return null;
  }
};
