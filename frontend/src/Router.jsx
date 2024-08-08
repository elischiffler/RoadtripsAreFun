import { createBrowserRouter } from "react-router-dom";
import HomePage from "./pages/HomePage/HomePage";
import ItineraryPage from "./pages/ItineraryPage";
import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage/ChatPage";
import MapPage from "./pages/MapPage";
import SettingsPage from "./pages/SettingsPage";
import SignUpPage from "./pages/SignUpPage";
import NotFoundPage from "./pages/NotFoundPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <HomePage />,
  },
  {
    path: "itinerary",
    element: <ItineraryPage />,
  },
  {
    path: "login",
    element: <LoginPage />,
  },
  {
    path: "map",
    element: <MapPage />,
  },
  {
    path: "settings",
    element: <SettingsPage />,
  },
  {
    path: "chat",
    element: <ChatPage />,
  },
  {
    path: "signup",
    element: <SignUpPage />,
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);

export default router;
