import { useContext, useEffect } from 'react';
import { UserDataContext } from '../states/UserDataContext';
import { initializeUserData } from './ChatPage/DatabaseUtils';

// Map and itinerary can be opened directly after a browser reload. Rehydrate
// the selected saved trip when the in-memory context starts empty.
export function useStoredTrip() {
  const { UserData, setUserData } = useContext(UserDataContext);

  useEffect(() => {
    const token = sessionStorage.getItem('accessToken');
    if (!token || UserData.chatlogs.chatdata.length) return;
    let cancelled = false;
    initializeUserData(token).then((result) => {
      if (cancelled || !result?.UserData?.chatlogs?.chatdata?.length) return;
      const logs = result.UserData.chatlogs;
      const selectedId = Number(sessionStorage.getItem('selectedChatId'));
      logs.currentId = logs.getChatDataById(selectedId) ? selectedId : logs.chatdata[0].chatId;
      setUserData(result.UserData);
    });
    return () => {
      cancelled = true;
    };
  }, [UserData, setUserData]);

  return UserData.chatlogs;
}
