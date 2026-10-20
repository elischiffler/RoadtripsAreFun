import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getStudioSession, unlockStudio } from '../../services/studioSession';
import {
  createStudy,
  downloadStudy,
  researchCatalog,
  savedStudies,
  studyRequest,
} from '../../services/studioResearch';
import {
  Heatmap,
  ResponseCurve,
  RowChart,
  StatusColumns,
  Tradeoff,
  UtilitySpread,
  UtilityBoxes,
} from './ResearchCharts';
import { distribution, format, METRICS, metricValue, paired } from './researchData';
import '../AlgorithmLab/AlgorithmLab.css';
import './StudioResearch.css';

export default function StudioResearch() {
  const [catalog, setCatalog] = useState(null);
  const [design, setDesign] = useState(null);
  const [studies, setStudies] = useState(savedStudies);
  const [selected, setSelected] = useState(() => savedStudies()[0] ?? null);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [password, setPassword] = useState('');
  const [session, setSession] = useState(getStudioSession);
  const [track, setTrack] = useState('solver');
  const [metric, setMetric] = useState('utility_mean');
  const [persona, setPersona] = useState('all');
  const [density, setDensity] = useState('all');
  const [curveTrip, setCurveTrip] = useState('medium-2d');
  const [curveDensity, setCurveDensity] = useState('2');
  const [parameter, setParameter] = useState('quality_loss');
  const [variant, setVariant] = useState('baseline');
  const [recordsOpen, setRecordsOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    researchCatalog(controller.signal)
      .then((value) => {
        setCatalog(value);
        setDesign(value.defaults);
      })
      .catch((e) => {
        if (e.name !== 'CanceledError') setError('Research settings are unavailable.');
      });
    const refresh = () => setSession(getStudioSession());
    window.addEventListener('studio-access-changed', refresh);
    window.addEventListener('focus', refresh);
    return () => {
      controller.abort();
      window.removeEventListener('studio-access-changed', refresh);
      window.removeEventListener('focus', refresh);
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let timer;
    let cursor = 0;
    const observations = new Map();
    const poll = async () => {
      let complete = false;
      try {
        const next = await studyRequest(selected, '', 'get', controller.signal, cursor);
        if (controller.signal.aborted) return;
        next.rows.forEach((row) => observations.set(row.id, row));
        cursor = next.cursor ?? 0;
        setData({ ...next, rows: [...observations.values()] });
        complete = next.state === 'complete';
        setConnectionError('');
      } catch (e) {
        if (!controller.signal.aborted)
          setConnectionError(
            e.response?.status === 404
              ? 'This study is unavailable on this server or its access key is missing.'
              : 'Connection lost. The background study continues; reconnecting…'
          );
      }
      if (!controller.signal.aborted && !complete) timer = setTimeout(poll, 5000);
    };
    setData(null);
    poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [selected]);

  const action = async (callback) => {
    setBusy(true);
    setError('');
    try {
      await callback();
    } catch (e) {
      setError(
        e.response?.data?.detail && typeof e.response.data.detail === 'string'
          ? e.response.data.detail
          : 'The action could not finish. Your existing results are retained.'
      );
    } finally {
      setBusy(false);
    }
  };
  const launch = () =>
    action(async () => {
      if (!getStudioSession()) {
        setSession(null);
        return;
      }
      const id = crypto.randomUUID();
      const study = await createStudy(id, design);
      setStudies(savedStudies());
      setSelected(study);
      await studyRequest(study, 'start', 'post');
    });
  const change = (key, value) => setDesign({ ...design, [key]: value });
  const toggle = (key, value) =>
    change(
      key,
      design[key].includes(value)
        ? design[key].filter((item) => item !== value)
        : [...design[key], value]
    );
  const combinations = design
    ? design.trips.length * design.personas.length * design.stops_per_day.length
    : 0;
  const variantCount = design
    ? 1 +
      design.quality_loss.filter((value) => value !== 0.1).length +
      design.detour_weight.filter((value) => value !== 1).length
    : 0;
  const liveCount = design?.pipeline ? combinations * design.repeats : 0;
  const solverCount = design?.solver ? combinations * design.solver_repeats * variantCount : 0;
  const trackRows = (data?.rows ?? []).filter((row) => row.track === track);
  const filtered = trackRows.filter(
    (row) =>
      (persona === 'all' || row.persona === persona) &&
      (density === 'all' || row.stops_per_day === Number(density)) &&
      (track !== 'solver' || row.variant === variant)
  );
  const runtime = distribution(trackRows.map((row) => row.runtime_seconds));
  const solverCounts = {};
  filtered.forEach((row) => {
    const key = row.solver_status || 'NOT_RUN';
    solverCounts[key] = (solverCounts[key] ?? 0) + 1;
  });
  const responseTrip = data?.design.trips.includes(curveTrip) ? curveTrip : data?.design.trips[0];
  const responseDensity = data?.design.stops_per_day.includes(Number(curveDensity))
    ? curveDensity
    : String(data?.design.stops_per_day[0]);
  const curves = trackRows.filter(
    (row) => row.trip === responseTrip && row.stops_per_day === Number(responseDensity)
  );
  const changeVariants = (data?.variants ?? []).filter((row) => row.parameter === parameter);
  const delta = changeVariants.length
    ? paired(curves, changeVariants.at(-1).id, 'utility_mean')
    : { n: 0 };
  const trips = catalog?.trips ?? [];
  const finished = data?.rows?.length ?? 0;
  const running = ['running', 'starting', 'pausing'].includes(data?.state);

  return (
    <main className="algorithm-lab studio-research">
      <header className="lab-title">
        <div>
          <span className="research-eyebrow">AI Studio</span>
          <h1>Trip research</h1>
          <p>Compare trip outcomes and solver settings.</p>
        </div>
        <Link to="/studio">Back to Studio</Link>
      </header>
      {error && (
        <p className="lab-warning" role="alert">
          {error}
        </p>
      )}
      {connectionError && (
        <p className="lab-warning" role="status">
          {connectionError}
        </p>
      )}
      <section className="research-launch" aria-label="Batch setup">
        {catalog?.execution_enabled === false && (
          <p role="status">
            Batch execution is off on this server. Existing results are still available.
          </p>
        )}
        <div>
          <h2>Run a study</h2>
          <p>
            <strong>{format(liveCount + solverCount, 0)}</strong> runs · {format(liveCount, 0)} live
            trips · {format(solverCount, 0)} solver trials
          </p>
          <p className="research-muted">
            Live trips use paid providers. Solver trials use the same 100 synthetic candidates, with
            no provider calls.
          </p>
        </div>
        {design && (
          <>
            <div className="research-controls">
              <label>
                Live repeats
                <input
                  type="number"
                  min="1"
                  max="10"
                  step="1"
                  value={design.repeats}
                  onChange={(e) => change('repeats', Number(e.target.value))}
                />
              </label>
              <label>
                Solver repeats
                <input
                  type="number"
                  min="1"
                  max="100"
                  step="1"
                  value={design.solver_repeats}
                  onChange={(e) => change('solver_repeats', Number(e.target.value))}
                />
              </label>
              <label>
                Departure
                <input
                  type="date"
                  value={design.departure_date}
                  onChange={(e) => change('departure_date', e.target.value)}
                />
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={design.pipeline}
                  onChange={(e) => change('pipeline', e.target.checked)}
                />
                Full pipeline
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={design.solver}
                  onChange={(e) => change('solver', e.target.checked)}
                />
                CP-SAT only
              </label>
            </div>
            <details className="research-settings">
              <summary>Study settings</summary>
              <div className="research-setting-grid">
                <fieldset>
                  <legend>Trips</legend>
                  {trips.map((trip) => (
                    <label key={trip.id}>
                      <input
                        type="checkbox"
                        checked={design.trips.includes(trip.id)}
                        onChange={() => toggle('trips', trip.id)}
                      />
                      {trip.label}
                    </label>
                  ))}
                </fieldset>
                <fieldset>
                  <legend>Personas</legend>
                  {catalog.personas.map((key) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={design.personas.includes(key)}
                        onChange={() => toggle('personas', key)}
                      />
                      {key}
                    </label>
                  ))}
                  <legend>Stops per target day</legend>
                  {[1, 2, 3].map((value) => (
                    <label key={value}>
                      <input
                        type="checkbox"
                        checked={design.stops_per_day.includes(value)}
                        onChange={() => toggle('stops_per_day', value)}
                      />
                      {value}
                    </label>
                  ))}
                </fieldset>
                <fieldset>
                  <legend>Allowed utility loss</legend>
                  {[0, 0.05, 0.1, 0.15, 0.2].map((value) => (
                    <label key={value}>
                      <input
                        type="checkbox"
                        checked={design.quality_loss.includes(value)}
                        onChange={() => toggle('quality_loss', value)}
                      />
                      {value * 100} percentage points
                    </label>
                  ))}
                </fieldset>
                <fieldset>
                  <legend>Detour weight</legend>
                  {[0.5, 1, 2].map((value) => (
                    <label key={value}>
                      <input
                        type="checkbox"
                        checked={design.detour_weight.includes(value)}
                        onChange={() => toggle('detour_weight', value)}
                      />
                      {value}
                    </label>
                  ))}
                  <p className="research-muted">
                    Baseline always included. One parameter changes at a time.
                  </p>
                </fieldset>
              </div>
            </details>
            {session ? (
              <button
                className="research-primary"
                disabled={
                  busy ||
                  running ||
                  catalog?.execution_enabled === false ||
                  !combinations ||
                  !Number.isInteger(design.repeats) ||
                  design.repeats < 1 ||
                  design.repeats > 10 ||
                  !Number.isInteger(design.solver_repeats) ||
                  design.solver_repeats < 1 ||
                  design.solver_repeats > 100 ||
                  (!design.pipeline && !design.solver) ||
                  !design.quality_loss.length ||
                  !design.detour_weight.length
                }
                onClick={launch}
              >
                {busy ? 'Starting…' : `Start ${format(liveCount + solverCount, 0)} runs`}
              </button>
            ) : (
              <form
                className="research-unlock"
                onSubmit={(e) => {
                  e.preventDefault();
                  action(async () => {
                    await unlockStudio(password);
                    setPassword('');
                    setSession(getStudioSession());
                  });
                }}
              >
                <label>
                  Studio password
                  <input
                    type="password"
                    autoComplete="off"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                <button disabled={busy}>Unlock batch runs</button>
              </form>
            )}
          </>
        )}
      </section>
      <div className="research-toolbar">
        <label>
          Study
          <select
            value={selected?.id ?? ''}
            onChange={(e) => setSelected(studies.find((row) => row.id === e.target.value) ?? null)}
          >
            <option value="">Choose a study</option>
            {studies.map((row, index) => (
              <option key={row.id} value={row.id}>
                Study {studies.length - index} · {row.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        {data && (
          <>
            <span className="research-state" role="status">
              {data.state} · {format(finished, 0)} / {format(data.counts.total, 0)}
            </span>
            {running ? (
              <button
                disabled={busy || data.state === 'pausing'}
                onClick={() => action(() => studyRequest(selected, 'pause', 'post'))}
              >
                Pause after current runs
              </button>
            ) : (
              data.state !== 'complete' && (
                <button
                  disabled={busy}
                  onClick={() => action(() => studyRequest(selected, 'start', 'post'))}
                >
                  Resume pending runs
                </button>
              )
            )}
            <button onClick={() => action(() => downloadStudy(selected, 'csv'))} disabled={busy}>
              Export CSV
            </button>
            <button onClick={() => action(() => downloadStudy(selected, 'json'))} disabled={busy}>
              Export JSON
            </button>
          </>
        )}
      </div>
      {!data ? (
        <section className="research-empty">
          <h2>A study starts with 30 combinations</h2>
          <p>Five trip types × two personas × one, two or three stops per target day.</p>
          <p>
            Ten live repeats make 300 trips. Thirty solver repeats across seven conditions add 6,300
            trials.
          </p>
        </section>
      ) : (
        <>
          <progress value={finished} max={data.counts.total} aria-label="Finished study runs" />
          <nav className="research-tabs" aria-label="Study track">
            <button
              aria-pressed={track === 'pipeline'}
              onClick={() => {
                setTrack('pipeline');
                setMetric('utility_mean');
              }}
            >
              Full pipeline · {data.counts.pipeline}
            </button>
            <button
              aria-pressed={track === 'solver'}
              onClick={() => {
                setTrack('solver');
                setMetric('utility_mean');
              }}
            >
              CP-SAT · {data.counts.solver}
            </button>
          </nav>
          <p className="research-muted">
            {track === 'pipeline'
              ? 'Fresh live trips. Utility describes delivered attractions with complete, fulfilled, timing-valid trips.'
              : `Controlled synthetic experiment · 100 fixed candidates · ${data.design.solver_repeats} seed repeats. Gap and detour values are model inputs, not measured road trips.`}
          </p>
          <div className="research-stat-row research-summary">
            <div>
              <span>Finished attempts</span>
              <strong>{format(trackRows.length, 0)}</strong>
            </div>
            <div>
              <span>Fully delivered</span>
              <strong>{format(trackRows.filter((row) => row.completed).length, 0)}</strong>
            </div>
            <div>
              <span>Failed / interrupted</span>
              <strong>
                {format(trackRows.filter((row) => row.outcome !== 'completed').length, 0)}
              </strong>
            </div>
            <div>
              <span>Median runtime</span>
              <strong>
                {format(runtime.median)}
                <small> sec</small>
              </strong>
            </div>
          </div>
          <div className="research-controls research-filters">
            <label>
              Metric
              <select value={metric} onChange={(e) => setMetric(e.target.value)}>
                {Object.entries(METRICS)
                  .filter(([, value]) => track === 'pipeline' || !value.live)
                  .map(([key, value]) => (
                    <option value={key} key={key}>
                      {value.label}
                      {key === 'max_gap_seconds' && track === 'solver' ? ' (baseline)' : ''}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Persona
              <select value={persona} onChange={(e) => setPersona(e.target.value)}>
                <option value="all">Both personas</option>
                <option value="nature">Nature</option>
                <option value="entertainment">Entertainment</option>
              </select>
            </label>
            <label>
              Stops / day
              <select value={density} onChange={(e) => setDensity(e.target.value)}>
                <option value="all">All rates</option>
                {[1, 2, 3].map((n) => (
                  <option value={n} key={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            {track === 'solver' && (
              <label>
                Condition
                <select value={variant} onChange={(e) => setVariant(e.target.value)}>
                  {data.variants.map((row) => (
                    <option value={row.id} key={row.id}>
                      {row.id === 'baseline'
                        ? 'Baseline'
                        : `${row.parameter === 'quality_loss' ? 'Utility loss' : 'Detour weight'}: ${row.value}`}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <section className="research-card">
            <Heatmap rows={filtered} trips={trips} metric={metric} />
            <p className="research-muted">
              n = assessed values / finished attempts. A dash means no assessed value. Utility is an
              estimate, not a visitor rating.
            </p>
          </section>
          <div className="research-chart-grid">
            <section className="research-card">
              <StatusColumns rows={filtered} trips={trips} />
            </section>
            <section className="research-card">
              <RowChart rows={filtered} trips={trips} metric={metric} />
            </section>
          </div>
          <section className="research-card">
            <UtilitySpread rows={filtered} />
          </section>
          <section className="research-card">
            <UtilityBoxes rows={filtered} trips={trips} />
          </section>
          {track === 'pipeline' ? (
            <section className="research-card">
              <Tradeoff rows={filtered} />
              <p className="research-muted">
                Nature ● · Entertainment ●. Hotel metrics refer only to the per-room, per-night
                target; trips without hotel quotes are unassessed.
              </p>
            </section>
          ) : (
            <section className="research-card">
              <h2>Parameter response</h2>
              <div className="research-controls">
                <label>
                  Trip
                  <select value={responseTrip} onChange={(e) => setCurveTrip(e.target.value)}>
                    {trips
                      .filter((trip) => data.design.trips.includes(trip.id))
                      .map((trip) => (
                        <option value={trip.id} key={trip.id}>
                          {trip.label}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  Stops per day
                  <select value={responseDensity} onChange={(e) => setCurveDensity(e.target.value)}>
                    {[1, 2, 3].map((n) => (
                      <option value={n} key={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Parameter
                  <select value={parameter} onChange={(e) => setParameter(e.target.value)}>
                    <option value="quality_loss">Allowed utility loss</option>
                    <option value="detour_weight">Detour weight</option>
                  </select>
                </label>
              </div>
              <ResponseCurve
                rows={curves}
                variants={data.variants}
                parameter={parameter}
                metric={metric}
              />
              {delta.n >= 5 && (
                <p className="research-finding">
                  At{' '}
                  {parameter === 'quality_loss'
                    ? `${format(changeVariants.at(-1).value * 100)} percentage points allowed loss`
                    : `${changeVariants.at(-1).value} detour weight`}
                  , average utility changed by {format(delta.mean)} percentage points versus
                  baseline across {delta.n} paired seed trials.
                </p>
              )}
              <p className="research-muted">
                Same candidates, persona, stop count and seed are paired. These repeats measure
                solver variation on one dataset; they are not independent real-world samples.
              </p>
            </section>
          )}
          <section className="research-card">
            <h2>Solver outcomes</h2>
            <div className="research-statuses">
              {Object.entries(solverCounts).map(([label, count]) => (
                <div key={label}>
                  <span>{label.replaceAll('_', ' ')}</span>
                  <strong>{count}</strong>
                </div>
              ))}
              {!filtered.length && <p>No finished attempts yet.</p>}
            </div>
          </section>
          <details
            className="research-card"
            onToggle={(event) => setRecordsOpen(event.currentTarget.open)}
          >
            <summary>Measurements and run records</summary>
            {recordsOpen && (
              <>
                <p>
                  Quality charts include fully delivered, timing-valid runs. Outcome charts include
                  failures, partial trips and interruptions. Metric sample sizes exclude missing
                  values. Target days determine requested stop count; actual trip length remains a
                  measured outcome. All participants use two adults, one room, the same departure
                  clock and no optional evening suggestions.
                </p>
                <p>
                  Solver baseline: at most 10 percentage points below the best available average
                  utility; spacing weight 1; detour weight 1; 5-second solve limit; one solver
                  worker. One factor changes at a time. Objective values are retained for
                  within-condition diagnosis, not pooled as a trip-quality score.
                </p>
                <p>
                  Revision {data.identity.revision} ·{' '}
                  {data.identity.dirty ? 'working changes recorded' : 'clean checkout'} · dataset{' '}
                  {data.dataset_hash.slice(0, 12)} · {data.identity.metric_version}
                </p>
                <div className="research-table-scroll">
                  <table>
                    <caption>Finished attempts</caption>
                    <thead>
                      <tr>
                        {[
                          'Trip',
                          'Persona',
                          'Stops/day',
                          'Repeat',
                          'Condition',
                          'Result',
                          'Utility %',
                          'Days',
                          'Delivered',
                          'Objective',
                          `${METRICS[metric].label} (${METRICS[metric].unit})`,
                        ].map((label) => (
                          <th key={label}>{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((row) => (
                        <tr key={row.id}>
                          <td>{row.trip}</td>
                          <td>{row.persona}</td>
                          <td>{row.stops_per_day}</td>
                          <td>{row.repeat}</td>
                          <td>{row.variant}</td>
                          <td title={row.error?.message}>
                            {row.solver_status} · {row.outcome}
                          </td>
                          <td>
                            {format(row.utility_mean == null ? null : row.utility_mean * 100)}
                          </td>
                          <td>
                            {format(row.actual_days, 0)} / {row.target_days}
                          </td>
                          <td>
                            {format(row.delivered, 0)} / {format(row.requested, 0)}
                          </td>
                          <td>{format(row.objective)}</td>
                          <td>{format(metricValue(row, metric), METRICS[metric].digits)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </details>
        </>
      )}
    </main>
  );
}
