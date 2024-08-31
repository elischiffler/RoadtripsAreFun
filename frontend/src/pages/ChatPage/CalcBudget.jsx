

export const calcBudget = async (duration) => {
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
      console.log(hotelCount)
      const minHotelBudget = hotelCount * 100
      return minHotelBudget
    }

