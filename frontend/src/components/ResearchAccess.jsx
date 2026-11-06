import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { refreshRoutingSettings, useRoutingSettings } from '../services/routingSettings';
import { useSessionStatus } from '../services/useSessionStatus';
import { DesignFrame, Sheet, ActionButton } from '../design';
import '../pages/SettingsPage.css';

/** Eligibility comes from the verified server capability, never a browser email claim. */
export default function ResearchAccess({ children }) {
  const { canSelect } = useRoutingSettings();
  const session = useSessionStatus();
  const [checking, setChecking] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setChecking(true);
    void refreshRoutingSettings().finally(() => {
      if (active) setChecking(false);
    });
    return () => {
      active = false;
    };
  }, [session.generation, attempt]);
  if (canSelect) return children;
  return (
    <DesignFrame className="settings-page">
      <main>
        <Sheet>
          <h1 className="rt-title">Account access</h1>
          {checking ? (
            <p role="status">Checking access…</p>
          ) : (
            <>
              <p role="alert">This workspace is unavailable for this account.</p>
              <ActionButton variant="secondary" onClick={() => setAttempt((value) => value + 1)}>
                Check access again
              </ActionButton>
            </>
          )}
          <Link to="/settings">Back to Settings</Link>
        </Sheet>
      </main>
    </DesignFrame>
  );
}
ResearchAccess.propTypes = { children: PropTypes.node.isRequired };
