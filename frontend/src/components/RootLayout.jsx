import { Outlet } from 'react-router-dom';
import GlobalHeader from './GlobalHeader';

export default function RootLayout() {
  return (
    <>
      <GlobalHeader />
      <Outlet />
    </>
  );
}
