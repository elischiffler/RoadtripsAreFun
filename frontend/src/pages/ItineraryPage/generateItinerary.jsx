import axios from 'axios';

export const generateItinerary = async (UserChatData) => {
    try{
        const data = {
            'route': UserChatData.route
        };
        const response = await axios.post(`${import.meta.env.VITE_BACKEND_SERVER}`, data);

        const itinerary = response.data;
        console.log("Generated itinerary: ", itinerary);
        return itinerary;
    }
    catch(error){
        // Log any errors encountered during the request
        console.error("Error generating the itinerary:", error);
    }
}