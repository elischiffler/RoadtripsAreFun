import axios from 'axios';
import { backendAuthConfig } from '../../services/backendAuth';

export const generateItinerary = async (route) => {
  try {
    const data = {
      route: route,
    };
    const response = await axios.post(
      `${import.meta.env.VITE_BACKEND_SERVER}generate-itinerary`,
      data,
      backendAuthConfig()
    );

    const itinerary = response.data;
    return itinerary;
  } catch (error) {
    // Log any errors encountered during the request
    console.error('Error generating the itinerary:', error);
    return null;
  }
};
