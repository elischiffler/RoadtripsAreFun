import { Outlet } from 'react-router-dom';
import GlobalHeader from './GlobalHeader';
import { useEffect } from 'react';
import { watchSession } from '../services/session';

export default function RootLayout() {
  useEffect(watchSession, []);
  return (
    <>
      <GlobalHeader />
      <Outlet />
    </>
  );
}
