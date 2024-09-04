import axios from 'axios';

export const calcHotelBudget = async (duration) => {
    // Generate the initial route and grab the routes duration
    let hotelCount = 0
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

export const calcGasBudget = async (duration, year, make, model) => {
  const carBudget = 10
  console.log(model)
  const carInfo = await getCarInfo(year, make, model)
  const mpg = carInfo['combination_mpg']
  console.log(mpg)
  return carBudget
}

const getCarInfo = async (year, make, model) => {
  try{
  const params ={
    'model': model,
    'make': make,
    'year': year
  }
  const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}get-car-details`, { params: params });
  const carInfo = response.data
  console.log(`Car Details: ${carInfo}`)
  return carInfo
  }
  catch(error){
    // Log any errors encountered during the request
    console.error("Error getting car info:", error);
    return null;
  }
}