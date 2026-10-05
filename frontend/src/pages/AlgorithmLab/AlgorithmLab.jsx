import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  useRoutingSettings,
  refreshRoutingSettings,
  invalidateRoutingSettings,
} from '../../services/routingSettings';
import { getLabPresets, runLab, labError } from '../../services/algorithmLab';
import TripInputs from './TripInputs';
import LabResults from './LabResults';
import HelpTip from './HelpTip';
import './AlgorithmLab.css';

function LabWorkspace() {
  const [catalog, setCatalog] = useState(null);
  const [presetId, setPresetId] = useState('');
  const [inputs, setInputs] = useState(null);
  const [mode, setMode] = useState('replay');
  const [snapshotId, setSnapshotId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [previous, setPrevious] = useState(null);
  const lastResult = useRef(null);
  const request = useRef(null);
  const output = useRef(null);
  const [reload, setReload] = useState(0);

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
        setSnapshotId(data.snapshots[0].id);
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
    setResult(null);
    setError('');
    try {
      const data = await runLab(
        {
          mode,
          preset_id: presetId,
          inputs,
          ...(mode === 'replay' ? { snapshot_id: snapshotId } : {}),
        },
        controller.signal
      );
      if (controller.signal.aborted || request.current !== controller) return;
      setPrevious(lastResult.current);
      setResult(data);
      lastResult.current = data;
    } catch (failure) {
      if (controller.signal.aborted || request.current !== controller) return;
      setError(labError(failure));
      if ([401, 403].includes(failure.response?.status)) invalidateRoutingSettings();
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
          'Loading authorized presets…'
        )}
      </div>
    );
  return (
    <div className="lab-layout">
      <form className="lab-input-panel" onSubmit={submit}>
        <div className="lab-controls">
          <label>
            Trip preset
            <select
              disabled={busy}
              value={presetId}
              onChange={(event) => choosePreset(event.target.value)}
            >
              {catalog.presets.map((preset) => (
                <option value={preset.id} key={preset.id}>
                  {preset.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Run mode
            <select
              disabled={busy}
              value={mode}
              onChange={(event) => {
                invalidate();
                setMode(event.target.value);
              }}
            >
              <option value="replay">Replay frozen candidates</option>
              <option value="live">Live providers</option>
            </select>
          </label>
          {mode === 'replay' && (
            <label>
              Candidate snapshot
              <select
                disabled={busy}
                value={snapshotId}
                onChange={(event) => {
                  invalidate();
                  setSnapshotId(event.target.value);
                }}
              >
                {catalog.snapshots.map((snapshot) => (
                  <option value={snapshot.id} key={snapshot.id}>
                    {snapshot.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p className="lab-note">
            {mode === 'replay'
              ? 'Frozen candidates. Change interests, then compare.'
              : 'Fresh places and a checked road route. This can take several minutes.'}{' '}
            <HelpTip label="run modes">
              Replay uses synthetic places and runs selection only. Live calls providers and builds
              a route. A failed live run never silently switches to replay.
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
            {busy ? 'Running…' : mode === 'replay' ? 'Run replay' : 'Run live route'}
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
          Temporary experiment; reloading clears it.{' '}
          <HelpTip label="experiment storage">
            Runs do not update account preferences or saved chats. Results remain in this page until
            reset, logout or reload.
          </HelpTip>
        </p>
      </form>
      <div
        className="lab-output-panel"
        aria-busy={busy}
        ref={output}
        tabIndex={-1}
        aria-label="Experiment output"
      >
        {busy && (
          <div className="lab-pending" role="status">
            <span className="lab-running-dot" />
            <h2>
              {mode === 'live' ? 'Building the route' : 'Solving the frozen candidate problem'}
            </h2>
            <p>
              {mode === 'live'
                ? 'Discovering candidates, matching profiles, selecting attractions, then scheduling and checking the drive.'
                : 'Normalizing weights, scoring candidates and running CP-SAT.'}
            </p>
          </div>
        )}
        {error && (
          <p role="alert" className="lab-error">
            {error} Update the inputs if needed, then run again.
          </p>
        )}
        {result && <LabResults key={result.snapshot.id} result={result} previous={previous} />}
        {!result && !busy && (
          <div className="lab-empty">
            <h2>Follow a trip from preferences to places.</h2>
            <p>
              Choose a preset and run the experiment to inspect the exact inputs, each place’s score
              and the solver’s decision.
            </p>
            <ol>
              <li>
                <strong>Trip profile</strong>
                <span>Where, when, who and what matters.</span>
              </li>
              <li>
                <strong>Location match</strong>
                <span>Trip weights × place ratings.</span>
              </li>
              <li>
                <strong>CP-SAT selection</strong>
                <span>Maximum match within stop and slot limits.</span>
              </li>
              <li>
                <strong>Route checks</strong>
                <span>Live scheduling, road timing and itinerary.</span>
              </li>
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AlgorithmLab() {
  const capability = useRoutingSettings();
  const session = JSON.stringify([
    sessionStorage.getItem('accessToken'),
    sessionStorage.getItem('idToken'),
  ]);
  return (
    <main className="algorithm-lab">
      <header className="lab-title">
        <div>
          <h1>Algorithm Lab</h1>
          <p>See why a road trip fits.</p>
        </div>
        <Link to="/chat">Back to trip chat</Link>
      </header>
      {capability.canSelect ? (
        <LabWorkspace key={session} />
      ) : (
        <div className="lab-access" role="status">
          <h2>Owner access required</h2>
          <p>
            Access is verified by the server. Sign in with the authorized owner account to load the
            demonstration.
          </p>
          <Link to="/login">Sign in</Link>
          <button onClick={() => refreshRoutingSettings()}>Check access again</button>
        </div>
      )}
    </main>
  );
}
