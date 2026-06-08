/**
 * testUtils.jsx — shared render helpers for the MyRoadtrip test suite.
 *
 * All components that consume MUI theme, UserDataContext, or react-router
 * must be rendered through `renderWithProviders` or one of the page-specific
 * helpers below.
 */
import React from 'react';
import { render } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { UserDataProvider } from '../states/UserDataContext';
import customTheme from '../components/Theme';

/**
 * Wraps a component with:
 *   - MUI ThemeProvider (earthy palette)
 *   - UserDataProvider (global trip state)
 *   - MemoryRouter at the given initialPath
 *
 * @param {ReactElement} ui
 * @param {object} [options]
 * @param {string} [options.initialPath='/']  – starting URL
 * @param {object} [options.renderOptions]    – forwarded to RTL render()
 */
export function renderWithProviders(ui, { initialPath = '/', renderOptions = {} } = {}) {
  function Wrapper({ children }) {
    return (
      <UserDataProvider>
        <ThemeProvider theme={customTheme}>
          <CssBaseline />
          <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
        </ThemeProvider>
      </UserDataProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

/**
 * Renders a full page component at a specific route path so that
 * `useLocation`, `useNavigate`, and route-matching all work.
 *
 * @param {string} path        – route pattern, e.g. '/chat'
 * @param {ReactElement} page  – the page element, e.g. <ChatPage />
 * @param {string} [at]        – the URL to start at (defaults to path)
 */
export function renderPage(path, page, at) {
  return renderWithProviders(
    <Routes>
      <Route path={path} element={page} />
    </Routes>,
    { initialPath: at ?? path }
  );
}
