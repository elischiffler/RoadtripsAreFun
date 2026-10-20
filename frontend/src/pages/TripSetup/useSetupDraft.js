import { useEffect, useState } from 'react';
import { getSession } from '../../services/session';
import { newSetupDraft, restoreDraft } from './setupModel';

export const SETUP_DRAFT_PREFIX = 'roadtrips.setup.v1.';

export default function useSetupDraft() {
  const [owner] = useState(() => getSession().owner);
  const [key] = useState(
    () => SETUP_DRAFT_PREFIX + encodeURIComponent(getSession().owner ?? 'anonymous')
  );
  const [restored] = useState(() => {
    try {
      return restoreDraft(sessionStorage.getItem(key));
    } catch {
      return null;
    }
  });
  const [draft, setDraft] = useState(() => restored?.draft ?? newSetupDraft());
  const [step, setStep] = useState(restored?.step ?? 0);
  const [stored, setStored] = useState(false);
  useEffect(() => {
    if (getSession().owner !== owner) return;
    try {
      sessionStorage.setItem(key, JSON.stringify({ version: 1, draft, step }));
      setStored(true);
    } catch {
      setStored(false);
    }
  }, [draft, step, key, owner]);
  useEffect(() => {
    const changed = () => {
      if (getSession().owner !== owner || getSession().status === 'signed-out') {
        sessionStorage.removeItem(key);
        setDraft(newSetupDraft());
        setStep(0);
        setStored(false);
      }
    };
    window.addEventListener('auth-changed', changed);
    return () => window.removeEventListener('auth-changed', changed);
  }, [key, owner]);
  return {
    draft,
    setDraft,
    step,
    setStep,
    stored,
    reset: () => {
      setDraft(newSetupDraft());
      setStep(0);
    },
  };
}
