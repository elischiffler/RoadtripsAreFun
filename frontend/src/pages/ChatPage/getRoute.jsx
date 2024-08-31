import axios from 'axios';
export const getInitialRoute = async(start_lat, start_lon, end_lat, end_lon)=> {
    try{
    const params = {
        'start_lat': start_lat,
        'start_lon': start_lon,
        'end_lat': end_lat,
        'end_lon': end_lon
    }
    const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}get-initial-route`, { params: params });
    }
    catch(error){
        // Log any errors encountered during the request
        console.error("Error creating initial route:", error);
        return null
    }
}
export const getFinalRoute = async (start_lat,
    start_lon,
    end_lat,
    end_lon,
    budget,
    stops,
) => {
    try{
        const params = {
            'start_lat': start_lat,
            'start_lon': start_lon,
            'end_lat': end_lat,
            'end_lon': end_lon,
            'budget': budget,
            'num_stops': stops,
        };

        // Send request for a route given the user inputs
        const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}get-final-route`, { params: params });

        // Access route information returned
        const route = response.data;
        duration = route.duration

        // Return route structure
        console.log("Specified route:", route);
        return duration;
    }
    catch(error){
        // Log any errors encountered during the request
        console.error("Error creating final route:", error);
        return null
    }
};