import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  useRoutingSettings,
  refreshRoutingSettings,
  invalidateRoutingSettings,
} from '../../services/routingSettings';
import { getLabPresets, runLab, labError } from '../../services/algorithmLab';
import TripInputs from './TripInputs';
import TripPresetDialog from './TripPresetDialog';
import LabResults from './LabResults';
import HelpTip from './HelpTip';
import RunHistory from './RunHistory';
import './AlgorithmLab.css';

function LabWorkspace() {
  const [catalog, setCatalog] = useState(null);
  const [presetId, setPresetId] = useState('');
  const [inputs, setInputs] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
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
    setResult(null);
    setError('');
    try {
      const data = await runLab(
        {
          mode: 'live',
          preset_id: presetId,
          inputs,
        },
        controller.signal
      );
      if (controller.signal.aborted || request.current !== controller) return;
      setPrevious(lastResult.current);
      setResult(data);
      lastResult.current = data;
      setHistoryRevision((value) => value + 1);
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
          <TripPresetDialog
            catalog={catalog}
            presetId={presetId}
            disabled={busy}
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
      <div
        className="lab-output-panel"
        hidden={!busy && !error && !result}
        aria-busy={busy}
        ref={output}
        tabIndex={-1}
        aria-label="Experiment output"
      >
        {busy && (
          <div className="lab-pending" role="status">
            <span className="lab-running-dot" />
            <h2>Building the route</h2>
            <p>
              Discovering candidates, matching profiles, selecting attractions, then scheduling and
              checking the drive.
            </p>
          </div>
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
        {result && <LabResults key={result.snapshot.id} result={result} previous={previous} />}
      </div>
      <RunHistory revision={historyRevision} />
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
