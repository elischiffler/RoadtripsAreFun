import axios from 'axios';
import { addMessage, removeLoader, handlePromptCarInfo, } from './startWorkFlow';

export const calcHotelBudget = async (route_duration, stops) => {
    // Generate the initial route and grab the routes duration
    let hotelCount = 0
    var duration = route_duration + stops*7200 // Can edit this number (set to 2 hours per stop)
      if (duration < 25200){   // Can edit this number (set to 7 hours driving per day)
        return 0
      } else {
        while (duration > 25200) {  // Can edit this number (set to 7 hours driving per day)
            hotelCount ++
            duration -= 25200  //Subtract a day worth of driving from duration
        }
      }
      const minHotelBudget = hotelCount * 100
      return minHotelBudget
    }

export const calcGasBudget = async (distanceInMeters, year, make, model, chatId, setChats, UserChatData) => {
  const carInfo = await getCarInfo(year, make, model, chatId, setChats, UserChatData)  // Get car info from backend
  if(carInfo){
    const mpg = carInfo['combination_mpg'];  // Grab the miles per gallon of the car
    const distanceInMiles = distanceInMeters * 0.000621371; // Turns the distance into miles
    const gasUsed = distanceInMiles / mpg;  // Calculate how much gas was used
    const gasBudget = gasUsed * 3.317; // 3.317 is the average price of gas in the US. Switch to a more specific number using api and user location in future
    UserChatData.carBudget = Math.round(gasBudget);
    return UserChatData;
  }else{
    await handlePromptCarInfo(chatId, setChats, UserChatData); // Loop through getting car info again
  }
}

const getCarInfo = async (year, make, model, chatId, setChats, UserChatData) => {
  try{
  const params ={
    'model': model,
    'make': make,
    'year': year
  }
  addMessage(chatId, setChats, "loading", 'bot');
  const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}get-car-details`, { params: params });
  removeLoader(chatId, setChats);
  const carInfo = response.data
  console.log(`Car Details: ${carInfo}`)
  return carInfo
  }
  catch(error){
    removeLoader(chatId, setChats);
    // Log any errors encountered during the request
    console.error("Error getting car info:", error);

    if (error.response.status === 500) {
      handleElectricCar(chatId, setChats)      
    } else {
      addMessage(chatId, setChats, 'We had an error getting your car information. Could you please re-enter your car information?', 'bot');
    }
    // Resets the input field
    UserChatData.carDetails = new Array(3).fill("")
    
    return null;
  }
}

const handleElectricCar = async (chatId, setChats) => {
  addMessage(chatId, setChats, 'We currently do not support creating a traveling budget with electric cars. Would you like to skip creating a gas budget or input a new car?', 'bot');
}
