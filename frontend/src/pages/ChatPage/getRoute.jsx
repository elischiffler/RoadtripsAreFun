import axios from 'axios';
export const getInitialRoute = async(start_lat, start_lon, end_lat, end_lon, UserChatData)=> {
    try{
    const params = {
        'start_lat': start_lat,
        'start_lon': start_lon,
        'end_lat': end_lat,
        'end_lon': end_lon,
    }
    const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}get-initial-route`, { params: params });
    const duration  = response.data
    return duration
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
            'num_stops': stops,
            'budget': budget,
        };

        // Send request for a route given the user inputs
        const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}get-final-route`, { params: params });

        // Access route information returned
        const route = response.data;

        // Return route structure
        console.log("Specified route:", route);
        return route;
    }
    catch(error){
        // Log any errors encountered during the request
        console.error("Error creating final route:", error);
        return null
    }
};