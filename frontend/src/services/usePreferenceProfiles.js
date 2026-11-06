import { useCallback, useEffect, useState } from 'react';
import { getSession } from './session';
import { loadPreferenceProfiles } from './preferenceProfiles';

// No cross-account cache. Stale requests cannot mount another account's data.
export default function usePreferenceProfiles() {
  const [owner, setOwner] = useState(() => getSession().owner);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ owner: null, profiles: [], loading: true, error: '' });
  useEffect(() => {
    const changed = () => {
      setOwner(getSession().owner);
      setAttempt((value) => value + 1);
    };
    window.addEventListener('auth-changed', changed);
    return () => window.removeEventListener('auth-changed', changed);
  }, []);
  useEffect(() => {
    let active = true;
    setState({ owner, profiles: [], loading: !!owner, error: '' });
    if (owner)
      loadPreferenceProfiles().then(
        (profiles) => {
          if (active && getSession().owner === owner)
            setState({ owner, profiles, loading: false, error: '' });
        },
        () => {
          if (active && getSession().owner === owner)
            setState({
              owner,
              profiles: [],
              loading: false,
              error: 'Saved preferences could not be loaded.',
            });
        }
      );
    return () => {
      active = false;
    };
  }, [owner, attempt]);
  const refresh = useCallback(() => setAttempt((value) => value + 1), []);
  return {
    ...(state.owner === getSession().owner ? state : { profiles: [], loading: true, error: '' }),
    refresh,
  };
}
