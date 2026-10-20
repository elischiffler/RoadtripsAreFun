import PropTypes from 'prop-types';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getStudioSession, unlockStudio } from '../../services/studioSession';
import { getLabPresets, runLab, labError } from '../../services/algorithmLab';
import TripInputs from './TripInputs';
import TripPresetDialog from './TripPresetDialog';
import LabResults from './LabResults';
import HelpTip from './HelpTip';
import RunHistory from './RunHistory';
import StudioProgress from './StudioProgress';
import HistoryDialog from './HistoryDialog';
import {
  readStudioWorkspace,
  saveStudioWorkspace,
  validStudioInputs,
} from '../../services/studioWorkspace';
import { getStudioJob, cancelStudioJob } from '../../services/studioJobs';
import './AlgorithmLab.css';

const defaultPreset = (catalog) =>
  catalog.presets.find((preset) => preset.id === 'medium-two-day') ?? catalog.presets[0];

function LabWorkspace({ historyOpen, onCloseHistory, session }) {
  const [restored] = useState(() => readStudioWorkspace(session));
  const [catalog, setCatalog] = useState(null);
  const [presetId, setPresetId] = useState(restored?.presetId ?? '');
  const [inputs, setInputs] = useState(restored?.inputs ?? null);
  const [tab, setTab] = useState(restored?.tab ?? 'route');
  const [job, setJob] = useState(restored?.job ?? null);
  const [result, setResult] = useState(restored?.result ?? null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [storageFailed, setStorageFailed] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [openingRun, setOpeningRun] = useState(null);
  const request = useRef(null);
  const historyRequest = useRef(null);
  const output = useRef(null);
  const [reload, setReload] = useState(0);
  const [historyRevision, setHistoryRevision] = useState(0);
  const pending = job?.phase === 'running';
  const locked = busy || pending;

  useEffect(() => {
    if (!result && !error && !busy) return;
    output.current?.focus({ preventScroll: true });
    output.current?.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, [result, error, busy]);

  const connect = async (nextJob, preserveTab = false) => {
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    setBusy(true);
    setError('');
    setProgress([]);
    try {
      let data;
      if (nextJob.phase === 'complete') {
        const status = await getStudioJob(nextJob.id, controller.signal);
        if (status.state !== 'complete')
          throw new Error(status.message || 'This trip could not be reopened. Check History.');
        data = status.result;
      } else {
        data = await runLab(
          nextJob.run,
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
          },
          nextJob.id
        );
      }
      if (controller.signal.aborted || request.current !== controller) return;
      setResult(data);
      setJob({ id: nextJob.id, phase: 'complete' });
      if (!preserveTab) setTab('route');
      setHistoryRevision((value) => value + 1);
    } catch (failure) {
      if (controller.signal.aborted || request.current !== controller) return;
      setError(failure.response ? labError(failure) : failure.message);
      if (failure.terminal || [400, 401, 403, 422].includes(failure.response?.status)) setJob(null);
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
      }
    }
  };
  const [progress, setProgress] = useState([]);

  useEffect(() => {
    const controller = new AbortController();
    getLabPresets(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        const preset =
          data.presets.find((item) => item.id === restored?.presetId) ?? defaultPreset(data);
        setCatalog(data);
        setPresetId(preset.id);
        setInputs(restored?.inputs ?? structuredClone(preset.inputs));
        if (restored?.job && !restored.result) void connect(restored.job, true);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(labError(failure));
      });
    return () => {
      controller.abort();
      request.current?.abort(); // Disconnect polling; the server job keeps running.
      historyRequest.current?.abort();
    };
    // Initialization is scoped to this mounted Studio visitor, not changing form values.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload]);

  useEffect(() => {
    if (!catalog || !inputs) return;
    setStorageFailed(!saveStudioWorkspace(session, { presetId, inputs, result, tab, job }));
  }, [catalog, session, presetId, inputs, result, tab, job]);

  useEffect(() => {
    if (!historyOpen) historyRequest.current?.abort();
  }, [historyOpen]);

  const invalidate = () => {
    request.current?.abort();
    request.current = null;
    setBusy(false);
    setResult(null);
    setJob(null);
    setTab('route');
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
    if (pending) {
      void connect(job, true);
      return;
    }
    const nextJob = {
      id: crypto.randomUUID(),
      phase: 'running',
      run: { mode: 'live', preset_id: presetId, inputs },
    };
    if (
      !saveStudioWorkspace(session, { presetId, inputs, tab: 'route', result: null, job: nextJob })
    ) {
      setError(
        'Enable storage for this tab before starting a trip, so it can reconnect after reload.'
      );
      return;
    }
    setResult(null);
    setTab('route');
    setJob(nextJob);
    void connect(nextJob);
  };
  const reset = async () => {
    if (pending) {
      setCancelling(true);
      try {
        await cancelStudioJob(job.id);
      } catch {
        setError('Could not confirm the run stopped. Reconnect or try cancelling again.');
        return;
      } finally {
        setCancelling(false);
      }
    }
    choosePreset(defaultPreset(catalog).id);
  };
  const openSavedRun = async (run) => {
    const controller = new AbortController();
    historyRequest.current?.abort();
    historyRequest.current = controller;
    setOpeningRun(run.id);
    setHistoryError('');
    try {
      const status = await getStudioJob(run.id, controller.signal);
      if (controller.signal.aborted) return;
      if (status.state !== 'complete') throw new Error(status.message || 'This trip is not ready.');
      const data = status.result;
      const preset =
        catalog.presets.find((item) => item.id === run.preset_id) ?? defaultPreset(catalog);
      const savedInputs = data.input_snapshot;
      setInputs(validStudioInputs(savedInputs) ? savedInputs : structuredClone(preset.inputs));
      setPresetId(preset.id);
      setResult(data);
      setJob({ id: run.id, phase: 'complete' });
      setTab('route');
      setError('');
      onCloseHistory();
    } catch (failure) {
      if (!controller.signal.aborted)
        setHistoryError(failure.response ? labError(failure) : failure.message);
    } finally {
      if (historyRequest.current === controller) {
        historyRequest.current = null;
        setOpeningRun(null);
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
        aria-busy={locked}
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
            disabled={locked}
            modified={
              JSON.stringify(inputs) !==
              JSON.stringify(catalog.presets.find((preset) => preset.id === presetId).inputs)
            }
            onSelect={choosePreset}
          />
          <p className="lab-note">
            Catalog places and a checked road route. Road routing and hotel offers use live
            providers and can take several minutes.{' '}
            <HelpTip label="live providers">
              Each run verifies cities, searches the catalog, selects attractions, and builds the
              road route and itinerary. Trips needing overnight stays also fetch current hotel
              offers.
            </HelpTip>
          </p>
        </div>
        <TripInputs inputs={inputs} catalog={catalog} onChange={changeInputs} disabled={locked} />
        <div className="lab-actions">
          <button
            type="submit"
            className="lab-run"
            disabled={busy || !Object.values(inputs.persona_weights).some((weight) => weight > 0)}
          >
            {busy ? 'Running…' : pending ? 'Reconnect run' : 'Run live route'}
          </button>
          <button type="button" onClick={reset} disabled={cancelling}>
            {cancelling ? 'Stopping…' : pending ? 'Cancel and reset' : 'Reset preset'}
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
            <p className="lab-note">Your route, itinerary and trip stats will appear here.</p>
          </div>
        )}
        {busy && <StudioProgress events={progress} />}
        {storageFailed && (
          <p role="status">
            This tab could not keep the trip locally. Saved results remain in History.
          </p>
        )}
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
        {result && (
          <LabResults
            key={result.snapshot.id}
            result={result}
            activeTab={tab}
            onTabChange={setTab}
          />
        )}
      </div>
      {historyOpen && (
        <HistoryDialog onClose={onCloseHistory}>
          {historyError && <p role="alert">{historyError}</p>}
          <RunHistory
            revision={historyRevision}
            onOpenRun={openSavedRun}
            openingRun={openingRun}
            disabled={locked}
          />
        </HistoryDialog>
      )}
    </div>
  );
}

LabWorkspace.propTypes = {
  historyOpen: PropTypes.bool.isRequired,
  onCloseHistory: PropTypes.func.isRequired,
  session: PropTypes.object.isRequired,
};

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
          <h1>AI Studio</h1>
          <p>Plan, compare and understand your trip.</p>
        </div>
        <div className="lab-header-actions">
          {session && (
            <button
              type="button"
              aria-expanded={historyOpen}
              aria-haspopup="dialog"
              aria-controls="lab-history-panel"
              onClick={() => setHistoryOpen(true)}
            >
              History
            </button>
          )}
          <Link to="/">Back to home page</Link>
        </div>
      </header>
      {session ? (
        <LabWorkspace
          key={session.token}
          session={session}
          historyOpen={historyOpen}
          onCloseHistory={() => setHistoryOpen(false)}
        />
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
