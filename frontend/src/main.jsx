import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import 'bootstrap/dist/css/bootstrap.css';
import { RouterProvider } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import customTheme from './components/Theme';
import GlobalStyles from './components/GlobalStyles';
import { CssBaseline } from '@mui/material';
import router from './Router';
import { UserDataProvider } from './states/UserDataContext';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <UserDataProvider>
      <ThemeProvider theme={customTheme}>
        <CssBaseline />
        <GlobalStyles />
        <RouterProvider router={router} />
      </ThemeProvider>
    </UserDataProvider>
  </React.StrictMode>
);
