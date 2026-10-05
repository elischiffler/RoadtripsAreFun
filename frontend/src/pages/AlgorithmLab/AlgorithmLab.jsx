import PropTypes from 'prop-types';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getStudioSession, unlockStudio, clearStudioSession } from '../../services/studioSession';
import { getLabPresets, runLab, labError } from '../../services/algorithmLab';
import TripInputs from './TripInputs';
import TripPresetDialog from './TripPresetDialog';
import LabResults from './LabResults';
import HelpTip from './HelpTip';
import RunHistory from './RunHistory';
import StudioProgress from './StudioProgress';
import './AlgorithmLab.css';

function LabWorkspace({ historyOpen }) {
  const [catalog, setCatalog] = useState(null);
  const [presetId, setPresetId] = useState('');
  const [inputs, setInputs] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState([]);
  const [result, setResult] = useState(null);
  const [previous, setPrevious] = useState(null);
  const lastResult = useRef(null);
  const request = useRef(null);
  const output = useRef(null);
  const [reload, setReload] = useState(0);
  const [historyRevision, setHistoryRevision] = useState(0);

  useEffect(() => {
    if (!result && !error && !busy) return;
    output.current?.focus({ preventScroll: true });
    output.current?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, [result, error, busy]);

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    getLabPresets(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setCatalog(data);
        setPresetId(data.presets[0].id);
        setInputs(structuredClone(data.presets[0].inputs));
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(labError(failure));
      });
    return () => {
      controller.abort();
      request.current?.abort();
    };
  }, [reload]);

  const invalidate = () => {
    request.current?.abort();
    request.current = null;
    setBusy(false);
    setResult(null);
    setError('');
  };
  const changeInputs = (next) => {
    invalidate();
    setInputs(next);
  };
  const choosePreset = (id) => {
    invalidate();
    setPresetId(id);
    setInputs(structuredClone(catalog.presets.find((preset) => preset.id === id).inputs));
  };
  const submit = async (event) => {
    event.preventDefault();
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setProgress([]);
    setResult(null);
    setError('');
    try {
      const data = await runLab(
        {
          mode: 'live',
          preset_id: presetId,
          inputs,
        },
        controller.signal,
        (event) => {
          if (
            !controller.signal.aborted &&
            request.current === controller &&
            event.type === 'progress'
          )
            setProgress((previous) => [
              ...previous.filter((item) => item.stage !== event.stage),
              event,
            ]);
        }
      );
      if (controller.signal.aborted || request.current !== controller) return;
      setPrevious(lastResult.current);
      setResult(data);
      lastResult.current = data;
      setHistoryRevision((value) => value + 1);
    } catch (failure) {
      if (controller.signal.aborted || request.current !== controller) return;
      setError(labError(failure));
      if ([401, 403].includes(failure.response?.status)) clearStudioSession();
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
      }
    }
  };

  if (!catalog)
    return (
      <div className="lab-loading" role="status">
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button onClick={() => setReload((value) => value + 1)}>Retry preset loading</button>
          </>
        ) : (
          'Loading trip presets…'
        )}
      </div>
    );
  return (
    <div className="lab-layout">
      <form
        className="lab-input-panel"
        aria-busy={busy}
        onSubmit={submit}
        onInvalid={(event) => {
          let section = event.target.closest('details');
          while (section) {
            section.open = true;
            section = section.parentElement.closest('details');
          }
        }}
      >
        <div className="lab-controls">
          <TripPresetDialog
            catalog={catalog}
            presetId={presetId}
            disabled={busy}
            modified={
              JSON.stringify(inputs) !==
              JSON.stringify(catalog.presets.find((preset) => preset.id === presetId).inputs)
            }
            onSelect={choosePreset}
          />
          <p className="lab-note">
            Fresh places and a checked road route. Every run calls live providers and can take
            several minutes.{' '}
            <HelpTip label="live providers">
              Each run verifies cities, discovers places, selects attractions, and builds the road
              route and itinerary. Trips needing overnight stays also fetch current hotel offers.
            </HelpTip>
          </p>
        </div>
        <TripInputs inputs={inputs} catalog={catalog} onChange={changeInputs} disabled={busy} />
        <div className="lab-actions">
          <button
            type="submit"
            className="lab-run"
            disabled={busy || !Object.values(inputs.persona_weights).some((weight) => weight > 0)}
          >
            {busy ? 'Running…' : 'Run live route'}
          </button>
          <button
            type="button"
            onClick={() => {
              lastResult.current = null;
              setPrevious(null);
              choosePreset(presetId);
            }}
          >
            {busy ? 'Cancel and reset' : 'Reset preset'}
          </button>
        </div>
        <p className="lab-note">
          Runs are saved to a separate experiment history.{' '}
          <HelpTip label="experiment storage">
            Runs do not update account preferences or saved chats. Inputs and measurements persist
            in run history after reload. Chat runs are not recorded here.
          </HelpTip>
        </p>
      </form>
      <div className="lab-output-panel" ref={output} tabIndex={-1} aria-label="Experiment output">
        {!busy && !error && !result && (
          <div className="lab-empty">
            <span className="lab-eyebrow">Your next experiment</span>
            <h2>Build a trip. See how it fits.</h2>
            <p>Choose a preset or adjust the trip inputs, then run a live route.</p>
            <p className="lab-note">
              Your route and itinerary will appear here. Explore the algorithm details when you want
              a closer look.
            </p>
          </div>
        )}
        {busy && <StudioProgress events={progress} />}
        {error && (
          <p role="alert" className="lab-error">
            {error} Update the inputs if needed, then run again.
          </p>
        )}
        {result?.run_record && (
          <p role="status" className="lab-note">
            {result.run_record.saved ? 'Run saved to history.' : result.run_record.warning}
          </p>
        )}
        {result && <LabResults key={result.snapshot.id} result={result} previous={previous} />}
      </div>
      <div id="lab-history-panel" className="lab-history-panel" hidden={!historyOpen}>
        {historyOpen && <RunHistory revision={historyRevision} />}
      </div>
    </div>
  );
}

LabWorkspace.propTypes = { historyOpen: PropTypes.bool.isRequired };

export default function AlgorithmLab() {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [session, setSession] = useState(getStudioSession);
  const [password, setPassword] = useState('');
  const [accessError, setAccessError] = useState('');
  const [unlocking, setUnlocking] = useState(false);
  useEffect(() => {
    const refresh = () => setSession(getStudioSession());
    window.addEventListener('studio-access-changed', refresh);
    window.addEventListener('focus', refresh);
    const timer = session
      ? setTimeout(refresh, Math.max(0, session.expires_at * 1000 - Date.now()))
      : null;
    return () => {
      clearTimeout(timer);
      window.removeEventListener('studio-access-changed', refresh);
      window.removeEventListener('focus', refresh);
    };
  }, [session]);
  const unlock = async (event) => {
    event.preventDefault();
    setUnlocking(true);
    setAccessError('');
    try {
      await unlockStudio(password);
      setPassword('');
    } catch (error) {
      setAccessError(
        error.response?.status === 401
          ? 'Incorrect password. Try again.'
          : 'Studio access is unavailable. Please try again.'
      );
    } finally {
      setUnlocking(false);
    }
  };
  return (
    <main className="algorithm-lab">
      <header className="lab-title">
        <div>
          <h1>Trip Planning Studio</h1>
          <p>See why a road trip fits.</p>
        </div>
        <div className="lab-header-actions">
          {session && (
            <button
              type="button"
              aria-expanded={historyOpen}
              aria-controls="lab-history-panel"
              onClick={() => setHistoryOpen((open) => !open)}
            >
              History
            </button>
          )}
          <Link to="/">Back to home page</Link>
        </div>
      </header>
      {session ? (
        <LabWorkspace key={session.token} historyOpen={historyOpen} />
      ) : (
        <form className="lab-access" onSubmit={unlock}>
          <h2>Enter Studio password</h2>
          <p>No account is needed. Enter the shared password to plan live trips.</p>
          <label htmlFor="studio-password">Password</label>
          <input
            id="studio-password"
            type="password"
            autoComplete="off"
            required
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={unlocking}
          />
          <button type="submit" disabled={unlocking}>
            {unlocking ? 'Checking…' : 'Enter Studio'}
          </button>
          {accessError && <p role="alert">{accessError}</p>}
        </form>
      )}
    </main>
  );
}
