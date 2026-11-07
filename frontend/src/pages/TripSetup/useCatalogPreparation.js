import { useEffect, useRef, useState } from 'react';
import { loadRouteAlternatives } from '../../services/routeAlternatives';
import { getSession, isCurrentSession } from '../../services/session';

/** This early request reads the admitted catalog only. It never starts planning or AI. */
export default function useCatalogPreparation(route, inputKey) {
  const [session, setSession] = useState(getSession);
  const [state, setState] = useState({ key: null, status: 'idle', places: [] });
  const cache = useRef(new Map());
  const key = route && inputKey ? `${session.owner}:${session.generation}:${inputKey}` : null;
  useEffect(() => {
    const changed = () => {
      const current = getSession();
      if (!isCurrentSession(session)) cache.current.clear();
      setSession(current);
    };
    window.addEventListener('auth-changed', changed);
    return () => window.removeEventListener('auth-changed', changed);
  }, [session]);
  useEffect(() => {
    if (!key || !route || !session.owner || !isCurrentSession(session)) {
      setState({ key, status: 'idle', places: [] });
      return;
    }
    const previous = cache.current.get(key);
    if (previous && Date.now() - previous.time < 60000) {
      setState({ key, status: 'ready', places: previous.places });
      return;
    }
    const controller = new AbortController();
    setState({ key, status: 'loading', places: [] });
    loadRouteAlternatives(route, controller.signal).then(
      ({ places }) => {
        if (controller.signal.aborted || !isCurrentSession(session)) return;
        cache.current.set(key, { places, time: Date.now() });
        while (cache.current.size > 4) cache.current.delete(cache.current.keys().next().value);
        setState({ key, status: 'ready', places });
      },
      () => {
        if (!controller.signal.aborted && isCurrentSession(session))
          setState({ key, status: 'unavailable', places: [] });
      }
    );
    return () => controller.abort();
  }, [key, route, session]);
  return state.key === key && isCurrentSession(session) ? state : { status: 'idle', places: [] };
}
