import { useEffect, useState } from 'react';
import { getSession } from './session';

export function useSessionStatus() {
  const [session, setSession] = useState(getSession);
  useEffect(() => {
    const changed = () => setSession(getSession());
    window.addEventListener('auth-changed', changed);
    return () => window.removeEventListener('auth-changed', changed);
  }, []);
  return session;
}
