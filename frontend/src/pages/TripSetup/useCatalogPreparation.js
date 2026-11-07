import { useEffect, useRef, useState } from 'react';
import {
  loadRoutePreparation,
  preparationRequest,
  preparationPlaces,
  tentativeAreas,
} from '../../services/routePreparation';
import { getSession, isCurrentSession } from '../../services/session';

const empty = { status: 'idle', places: [], areas: [], sections: 0 };
/** Read-only, bounded catalog preparation; never planning, hotel quotes or AI. */
export default function useCatalogPreparation(route, inputKey, draft) {
  const [session, setSession] = useState(getSession);
  const [state, setState] = useState(empty);
  const cache = useRef(new Map());
  const payload = preparationRequest(route, draft);
  const serialized = payload ? JSON.stringify(payload) : null;
  const key =
    serialized && inputKey
      ? JSON.stringify([session.owner, session.generation, inputKey, draft?.date, serialized])
      : null;
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
    if (!key || !session.owner || !isCurrentSession(session)) {
      setState({ ...empty, key });
      return;
    }
    const previous = cache.current.get(key);
    if (previous && Date.now() - previous.time < 60000) {
      setState({ ...previous.value, key });
      return;
    }
    const controller = new AbortController();
    const current = () => !controller.signal.aborted && isCurrentSession(session);
    setState({ ...empty, key, status: 'loading' });
    const timer = setTimeout(
      () =>
        loadRoutePreparation(JSON.parse(serialized), controller.signal, (event) => {
          if (!current()) return;
          if (event.stage === 'preparation.areas' && event.preview_only === true)
            setState((old) => ({ ...old, areas: tentativeAreas(event.possible_overnight_areas) }));
          if (
            event.stage === 'preparation.catalog' &&
            Number.isInteger(event.sections_checked) &&
            event.sections_checked >= 0 &&
            event.sections_checked <= 6
          )
            setState((old) => ({
              ...old,
              places: preparationPlaces(event.places),
              sections: event.sections_checked,
            }));
        }).then(
          (result) => {
            if (!current()) return;
            const value = {
              status: ['ready', 'partial', 'unavailable'].includes(result?.catalog_status)
                ? result.catalog_status
                : 'unavailable',
              places: preparationPlaces(result?.places),
              areas: tentativeAreas(result?.possible_overnight_areas),
              sections: result?.sections_checked ?? 0,
            };
            // Source outages remain retryable rather than cached as a successful lookup.
            if (value.status === 'ready') {
              cache.current.set(key, { value, time: Date.now() });
              while (cache.current.size > 4)
                cache.current.delete(cache.current.keys().next().value);
            }
            setState({ ...value, key });
          },
          () => {
            if (current()) setState((old) => ({ ...old, status: 'unavailable' }));
          }
        ),
      400
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [key, serialized, session]);
  return state.key === key && isCurrentSession(session) ? state : empty;
}
