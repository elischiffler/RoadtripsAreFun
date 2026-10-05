import PropTypes from 'prop-types';
import { useEffect, useRef, useState } from 'react';
import { runLab, labError } from '../../services/algorithmLab';

export default function BenchmarkDialog({ catalog, disabled, onBusy, onResult }) {
  const dialog = useRef(null);
  const stopped = useRef(false);
  const mounted = useRef(true);
  const [selected, setSelected] = useState([]);
  const [repeats, setRepeats] = useState(1);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    mounted.current = true;
    return () => {
      stopped.current = true;
      mounted.current = false;
    };
  }, []);
  const start = async () => {
    if (busy || !selected.length) return;
    stopped.current = false;
    setBusy(true);
    onBusy(true);
    setError('');
    const batchId = crypto.randomUUID();
    const queue = selected.flatMap((id) =>
      Array.from({ length: repeats }, (_, index) => ({
        preset: catalog.benchmarks.find((item) => item.id === id),
        index: index + 1,
      }))
    );
    let completed = 0;
    try {
      for (const { preset, index } of queue) {
        if (stopped.current) break;
        setProgress(`Running ${completed + 1} of ${queue.length}: ${preset.label}`);
        const result = await runLab({
          mode: 'live',
          preset_id: preset.id,
          inputs: preset.inputs,
          batch_id: batchId,
          repeat_index: index,
        });
        if (!mounted.current) break;
        completed += 1;
        onResult(result);
        if (!result.run_record?.saved) {
          throw new Error('Result storage failed. Batch stopped to avoid unrecorded experiments.');
        }
      }
      if (mounted.current)
        setProgress(
          `${completed} of ${queue.length} runs finished${stopped.current ? '; remaining runs stopped' : ''}.`
        );
    } catch (failure) {
      if (mounted.current) setError(failure.response ? labError(failure) : failure.message);
    } finally {
      if (mounted.current) {
        setBusy(false);
        onBusy(false);
      }
    }
  };
  return (
    <>
      <button type="button" disabled={disabled} onClick={() => dialog.current.showModal()}>
        Benchmark trips
      </button>
      <dialog
        ref={dialog}
        className="lab-benchmark-dialog"
        aria-labelledby="benchmark-title"
        onCancel={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <h2 id="benchmark-title">Choose benchmark trips</h2>
        <p className="lab-note">
          Targets for comparison; actual drive times, stop counts and overnights depend on provider
          results.
        </p>
        <fieldset disabled={busy}>
          <legend>Trip set</legend>
          {(catalog.benchmarks || []).map((preset) => (
            <label className="lab-benchmark-choice" key={preset.id}>
              <input
                type="checkbox"
                checked={selected.includes(preset.id)}
                onChange={(event) =>
                  setSelected(
                    event.target.checked
                      ? [...selected, preset.id]
                      : selected.filter((id) => id !== preset.id)
                  )
                }
              />
              <span>
                <strong>{preset.label}</strong>
                <small>{preset.description}</small>
              </span>
            </label>
          ))}
          <label>
            Runs per trip
            <select value={repeats} onChange={(event) => setRepeats(Number(event.target.value))}>
              {[1, 3, 5, 10].map((count) => (
                <option key={count} value={count}>
                  {count}
                </option>
              ))}
            </select>
          </label>
        </fieldset>
        <p className="lab-note">
          CP-SAT is the active solver. Every experiment calls live providers for fresh discovery and
          a checked route. AI discovery can vary between repeated runs.
        </p>
        {progress && <p role="status">{progress}</p>}
        {error && <p role="alert">{error}</p>}
        <div className="lab-actions">
          <button type="button" disabled={busy || !selected.length} onClick={start}>
            Run {selected.length * repeats} experiments sequentially
          </button>
          {busy ? (
            <button
              type="button"
              onClick={() => {
                stopped.current = true;
                setProgress('Stopping after the current run is saved…');
              }}
            >
              Stop after current run
            </button>
          ) : (
            <button type="button" onClick={() => dialog.current.close()}>
              Close
            </button>
          )}
        </div>
        <p className="lab-note">
          Keep this page open to finish the queue. Leaving stops future runs; a request already sent
          may finish on the server.
        </p>
      </dialog>
    </>
  );
}

BenchmarkDialog.propTypes = {
  catalog: PropTypes.shape({ benchmarks: PropTypes.arrayOf(PropTypes.object) }).isRequired,
  disabled: PropTypes.bool,
  onBusy: PropTypes.func.isRequired,
  onResult: PropTypes.func.isRequired,
};
