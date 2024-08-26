import axios from 'axios';

export const getRoute = async (start_lat,
    start_lon,
    end_lat,
    end_lon,
    stops,
) => {
    try{
        const params = {
            'start_lat': start_lat,
            'start_lon': start_lon,
            'end_lat': end_lat,
            'end_lon': end_lon,
            'num_stops': stops,
        };

        // Send request for a route given the user inputs
        const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}get-route`, { params: params });

        // Access route information returned
        const route = response.data;

        // Return route structure
        console.log("Specified route:", route);
        return route;
    }
    catch(error){
        // Log any errors encountered during the request
        console.error("Error creating a route:", error);
        return null
    }
};