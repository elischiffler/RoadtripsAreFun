// Test-only browser harness. Synthetic identity and intercepted persistence;
// it is not a Cognito/API/database acceptance test or a production route.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import TripVisitProgress from "../../frontend/src/components/TripVisitProgress";
import {
  ChatData,
  ChatLogs,
  Data,
  UserDataContext,
} from "../../frontend/src/states/UserDataContext";
import { fixtureSession } from "../../frontend/src/tests/sessionFixtures";
fixtureSession("arrival-browser");
function makeTrip() {
  const trip = new ChatData(731);
  const now = Date.now();
  const stop = {
    provider_id: "fixture:arrival",
    name: "Synthetic arrival garden",
    type: "stop",
    kind: "arrival",
    coordinates: [40, -105],
    arrival_time: new Date(now).toISOString(),
    departure_time: new Date(now + 45 * 60000).toISOString(),
  };
  trip.route = {
    departure_time: new Date(now - 30 * 60000).toISOString(),
    stops: [
      stop,
      {
        ...stop,
        provider_id: "fixture:second",
        name: "Synthetic second garden",
        arrival_time: new Date(now + 45 * 60000).toISOString(),
        departure_time: new Date(now + 90 * 60000).toISOString(),
      },
    ],
  };
  trip.itinerary = [
    {
      date: "Synthetic travel day",
      stops: trip.route.stops.map((item) => ({
        ...item,
        coordinates: undefined,
      })),
    },
  ];
  trip.savedRevision = "a".repeat(64);
  trip.presentation = { visitedStopIds: [], futureField: "preserve" };
  return trip;
}
function Fixture() {
  const [UserData, setUserData] = useState(
    () => new Data(new ChatLogs([makeTrip()], 731)),
  );
  return (
    <main
      className="rt-design"
      style={{
        maxWidth: "42rem",
        margin: "auto",
        padding: "var(--rt-space-4)",
      }}
    >
      <UserDataContext.Provider
        value={{ UserData, setUserData, chats: [{ id: 731, messages: [] }] }}
      >
        <TripVisitProgress trip={UserData.chatlogs.chatdata[0]} />
      </UserDataContext.Provider>
    </main>
  );
}
createRoot(document.getElementById("root")).render(<Fixture />);
