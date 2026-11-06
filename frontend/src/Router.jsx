import { createBrowserRouter, Navigate } from 'react-router-dom';
import AuthWrapper from './components/AuthWrapper';
import RootLayout from './components/RootLayout';
import HomePage from './pages/HomePage/HomePage';
import TripPage from './pages/TripPage/TripPage';
import EditItineraryPage from './pages/EditItineraryPage/EditItineraryPage';
import ItineraryPage from './pages/ItineraryPage/ItineraryPage';
import LoginPage from './pages/AuthPages/LoginPage';
import SavedTripsPage from './pages/SavedTripsPage';
import MapPage from './pages/MapPage/MapPage';
import SettingsPage from './pages/SettingsPage';
import AlgorithmLab from './pages/AlgorithmLab/AlgorithmLab';
import SignUpPage from './pages/AuthPages/SignUpPage';
import NotFoundPage from './pages/NotFoundPage';
import TripSetupPage from './pages/TripSetup/TripSetupPage';
import ResearchRoute from './pages/StudioResearch/ResearchRoute';
import ResearchAccess from './components/ResearchAccess';

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: 'plan',
        element: (
          <AuthWrapper>
            <TripSetupPage />
          </AuthWrapper>
        ),
      },
      {
        path: '/',
        element: <HomePage />,
      },
      {
        path: 'trip',
        element: (
          <AuthWrapper>
            <TripPage />
          </AuthWrapper>
        ),
      },
      {
        path: 'itinerary/edit',
        element: (
          <AuthWrapper>
            <EditItineraryPage />
          </AuthWrapper>
        ),
      },
      {
        path: 'itinerary',
        element: (
          <AuthWrapper>
            <ItineraryPage />
          </AuthWrapper>
        ),
      },
      {
        path: 'login',
        element: <LoginPage />,
      },
      {
        path: 'map',
        element: (
          <AuthWrapper>
            <MapPage />
          </AuthWrapper>
        ),
      },
      {
        path: 'studio',
        element: (
          <AuthWrapper>
            <ResearchAccess>
              <AlgorithmLab />
            </ResearchAccess>
          </AuthWrapper>
        ),
      },
      {
        path: 'studio/research',
        element: (
          <AuthWrapper>
            <ResearchAccess>
              <ResearchRoute />
            </ResearchAccess>
          </AuthWrapper>
        ),
      },
      { path: 'algorithm', element: <Navigate to="/studio" replace /> },
      {
        path: 'settings',
        element: (
          <AuthWrapper>
            <SettingsPage />
          </AuthWrapper>
        ),
      },
      {
        path: 'trips',
        element: (
          <AuthWrapper>
            <SavedTripsPage />
          </AuthWrapper>
        ),
      },
      { path: 'chat', element: <Navigate to="/trips" replace /> },
      {
        path: 'signup',
        element: <SignUpPage />,
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
]);

export default router;
