import { Fragment, useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import PropTypes from 'prop-types';
import { ensureSession, getSession, safeReturnPath } from '../services/session';
import { useSessionStatus } from '../services/useSessionStatus';

const AuthWrapper = ({ children }) => {
  const location = useLocation();
  const session = useSessionStatus();
  const [restored, setRestored] = useState(false);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    ensureSession()
      .then(() => {
        if (!cancelled) {
          setRestored(true);
          setError(null);
        }
      })
      .catch((failure) => {
        if (!cancelled) setError(failure);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt, session.generation]);

  if (['/', '/login', '/signup'].includes(location.pathname)) return children;
  if (
    session.status === 'signin-required' ||
    session.status === 'signed-out' ||
    error?.code === 'signin-required'
  ) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          returnTo: safeReturnPath(location.pathname + location.search),
          sessionExpired: !!getSession().owner,
        }}
      />
    );
  }
  if (error && !restored)
    return (
      <div role="alert">
        Session renewal is temporarily unavailable. Your trip and message are kept.
        <button
          onClick={() => {
            setError(null);
            setAttempt((value) => value + 1);
          }}
        >
          Retry
        </button>
      </div>
    );
  if (!restored) return <p role="status">Restoring your session...</p>;
  return (
    <>
      {session.status === 'unavailable' && (
        <div role="alert">
          Session renewal is temporarily unavailable. Please retry in a few seconds. Your trip and
          message are kept.
          <button onClick={() => setAttempt((value) => value + 1)}>Retry session</button>
        </div>
      )}
      <Fragment key={session.owner}>{children}</Fragment>
    </>
  );
};

AuthWrapper.propTypes = { children: PropTypes.node.isRequired };
export default AuthWrapper;
