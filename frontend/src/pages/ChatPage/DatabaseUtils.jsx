import axios from 'axios';
import { Data, ChatLogs, ChatData, } from '../../states/UserDataContext';

export const createChat = async (auth_token, UserChatData, ChatLog) => {
    try{
        const data = {
            'PartitionKey': auth_token,
            'ChatData': UserChatData,
            'ChatLog': ChatLog
        };
        response = await axios.post(`${import.meta.env.VITE_BACKEND_SERVER}chats/create/${UserChatData.chatId}`, data);
        console.log('Successfully stored new chat in database:', response);
        return null;
    }
    catch(error){
        console.log('Error creating a new chat in the database:', error);
        return null;
    }
}

export const deleteChat = async(auth_token, chatId) => {
    try{
        const params = {
            'partition_key':  auth_token
        }
        await axios.delete(`${import.meta.env.VITE_BACKEND_SERVER}chats/delete/${chatId}`, {params})
        .then(console.log(response => console.log('Successfully deleted chat:', response)));
        return null
    }
    catch(error){
        console.log('Failed to delete chat:', error);
        return null;
    }
}

export const initializeUserData = async(auth_token) => {
    try{
        const params = {
            'partition_key': auth_token
        }
        const response = await axios.get(`${import.meta.env.VITE_BACKEND_SERVER}chats`, params)
        const user_data = response.data;
        var chats = []
        var chatdata = []
        for(i = 0; i < user_data.length; i++){
            chats.push(user_data[i][1]);
            chat_d = user_data[i][0];
            chatdata.push(new ChatData(
                chat_d['chatId'],
                chat_d['action'],
                chat_d['locationType'],
                chat_d['startCoords'],
                chat_d['startAddress'],
                chat_d['endCoords'],
                chat_d['endAddress'],
                chat_d['stops'],
                chat_d['showInputBar'],
                chat_d['showStopSlider'],
                chat_d['showBudgetSlider'],
                chat_d['showAddressInput'],
                false,
                chat_d['startConfirmed'],
                chat_d['endConfirmed'],
                chat_d['initial'],
                chat_d['route'],
                chat_d['itinerary'],
                false, 
                chat_d['hotelBudget'],
                chat_d['carBudget'],
                chat_d['carDetails'],
                chat_d['budget'],
            ));
        }
        const logs = new ChatLogs(chatdata);
        const UserData = new Data(logs);
        return {'chats': chats, 'UserData': UserData};
    }
    catch(error){
        console.log('Error retrieving saved chats:', error);
    }
};

