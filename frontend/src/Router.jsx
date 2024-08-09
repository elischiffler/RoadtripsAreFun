import { createBrowserRouter } from "react-router-dom";
import AuthWrapper from "./components/AuthWrapper";
import HomePage from "./pages/HomePage/HomePage";
import ItineraryPage from "./pages/ItineraryPage/ItineraryPage";
import LoginPage from "./pages/AuthPages/LoginPage";
import ChatPage from "./pages/ChatPage/ChatPage";
import MapPage from "./pages/MapPage/MapPage";
import SettingsPage from "./pages/SettingsPage";
import SignUpPage from "./pages/AuthPages/SignUpPage";
import NotFoundPage from "./pages/NotFoundPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <HomePage />,
  },
  {
    path: "itinerary",
    element: (
      <AuthWrapper>
        <ItineraryPage />
      </AuthWrapper>
    ),
  },
  {
    path: "login",
    element: <LoginPage />,
  },
  {
    path: "map",
    element: (
      <AuthWrapper>
        <MapPage />
      </AuthWrapper>
    ),
  },
  {
    path: "settings",
    element: (
      <AuthWrapper>
        <SettingsPage />
      </AuthWrapper>
    ),
  },
  {
    path: "chat",
    element: (
      <AuthWrapper>
        <ChatPage />
      </AuthWrapper>
    ),
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
