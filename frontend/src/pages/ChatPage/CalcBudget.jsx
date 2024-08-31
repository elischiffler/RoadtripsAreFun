import { getInitialRoute } from "./getRoute";

const calcBudget = async () => {
    // Generate the initial route and grab the routes duration
    duration = await getInitialRoute(UserChatData.startConfirmed['latitude'],
        UserChatData.startConfirmed['longitude'],
        UserChatData.endConfirmed['latitude'],
        UserChatData.endConfirmed['longitude']
      );
    }

    