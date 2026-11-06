import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import 'bootstrap/dist/css/bootstrap.css';
import { RouterProvider } from 'react-router-dom';
import AppTheme from './components/AppTheme';
import router from './Router';
import { UserDataProvider } from './states/UserDataContext';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <UserDataProvider>
      <AppTheme>
        <RouterProvider router={router} />
      </AppTheme>
    </UserDataProvider>
  </React.StrictMode>
);
