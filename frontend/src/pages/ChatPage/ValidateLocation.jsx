import axios from 'axios';
import { addMessage, inputLocationWorkflow } from "./startWorkFlow"

// Sends an API request to our backend to validate the location
// It takes a starting location and a flag indicating whether the location is a coordinate or an address
export const validateLocation = async (input, isCoordinate, UserChatData, setChats, setChatInput, chatInput) => {
try {
    // Construct the query parameter based on whether the input is a coordinate or an address
    const data = isCoordinate
    ? {'location': {'coordinates': input}, is_coordinates: isCoordinate}
    : {'location' : {'address' : input}, is_coordinates: isCoordinate};
    
    UserChatData.loading = true  // Start a loading chat animation
    // Send the a post request to the backend server
    const response = await axios.post(`${import.meta.env.VITE_BACKEND_SERVER}validate-location`, data);
    UserChatData.loading = false// Delete the loading chat animation

    // Get the exact address
    const location =  response.data;
    console.log("Validated Location:", location);

    // Return the location data
    return location;
} catch (error) {
    UserChatData.loading = false
    // Log any errors encountered during the request
    console.error("Error validating location:", error);
    addMessage(UserChatData.chatId, setChats, "Error finding the location. Please try again.")

    //Set values back to regular
    UserChatData.action = null
    // Re-trigger the workflow
    inputLocationWorkflow(UserChatData.chatId, setChats, setChatInput, chatInput, UserChatData)
}
};

