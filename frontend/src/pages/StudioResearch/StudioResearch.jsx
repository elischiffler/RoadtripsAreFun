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
import { distribution, format, METRICS, paired } from './researchData';
import ResearchInfo, { ChartHeading } from './ResearchInfo';
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
      <details className="research-launch" aria-label="Batch setup" open={!selected}>
        <summary>New study</summary>
        <div className="research-launch-body">
          {catalog?.execution_enabled === false && (
            <p role="status">
              Batch execution is off on this server. Existing results are still available.
            </p>
          )}
          <div>
            <p>
              <strong>{format(liveCount + solverCount, 0)}</strong> runs · {format(liveCount, 0)}{' '}
              live trips · {format(solverCount, 0)} solver trials
            </p>
            <ResearchInfo label="Study setup">
              Live trips use paid providers. CP-SAT trials use the same 100 synthetic candidates
              without provider calls. The baseline is always included; each other condition changes
              one parameter at a time. Runs continue after navigation or closing the browser.
            </ResearchInfo>
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
        </div>
      </details>
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
                Pause
              </button>
            ) : (
              data.state !== 'complete' && (
                <button
                  disabled={busy}
                  onClick={() => action(() => studyRequest(selected, 'start', 'post'))}
                >
                  Resume
                </button>
              )
            )}
            <button
              aria-label="Export CSV"
              onClick={() => action(() => downloadStudy(selected, 'csv'))}
              disabled={busy}
            >
              CSV
            </button>
            <button
              aria-label="Export JSON"
              onClick={() => action(() => downloadStudy(selected, 'json'))}
              disabled={busy}
            >
              JSON
            </button>
          </>
        )}
      </div>
      {!data ? (
        <p className="research-empty">{selected ? 'Loading…' : 'Select or create a study.'}</p>
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
          <div className="research-track-meta">
            <span>
              {track === 'pipeline'
                ? 'Live trips'
                : `100 synthetic candidates · ${data.design.solver_repeats} repeats`}
            </span>
            <ResearchInfo label="Study data">
              {track === 'pipeline'
                ? 'Fresh live trips through the complete pipeline. Quality scores require fully delivered, timing-valid itineraries. Hotel metrics cover quoted room-nights only, not the total trip budget. Missing quotes are unassessed.'
                : 'Controlled trials on one fixed synthetic dataset. Gap and detour inputs are simulated, not measured journeys. Repeats change solver seeds; they are not independent real-world samples. The baseline allows 10 percentage points of utility loss, spacing weight 1, detour weight 1, a five-second limit and one worker.'}{' '}
              Summary totals cover all settings in this track; charts below follow their filters.
              Target days set requested stops, not actual trip length. Pausing finishes current
              runs.
            </ResearchInfo>
          </div>
          <div className="research-stat-row research-summary">
            <div>
              <span>Finished</span>
              <strong>{format(trackRows.length, 0)}</strong>
            </div>
            <div>
              <span>Complete</span>
              <strong>{format(trackRows.filter((row) => row.completed).length, 0)}</strong>
            </div>
            <div>
              <span>Failed / interrupted</span>
              <strong>
                {format(trackRows.filter((row) => row.outcome !== 'completed').length, 0)}
              </strong>
            </div>
            <div>
              <span>Median time</span>
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
                        : row.parameter === 'quality_loss'
                          ? `Allowed loss: ${format(row.value * 100)} points`
                          : `Detour weight: ${row.value}`}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <section className="research-card">
            <Heatmap rows={filtered} trips={trips} metric={metric} />
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
            </section>
          ) : (
            <section className="research-card">
              <ChartHeading
                as="h2"
                title="Parameter response"
                help="Mean of the selected metric as one solver setting changes. Trip and stops per day stay fixed here; persona and condition filters above do not apply. Points show each persona separately; hover a point for sample size and spread. Allowed loss is the permitted drop from the best available average utility. The same candidates and seed are paired across settings; these are repeated solver trials on one dataset."
              />
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
                <div className="research-finding">
                  <span>
                    Utility change: {format(delta.mean)} points · n={delta.n}
                  </span>
                  <ResearchInfo label="Utility change">
                    {parameter === 'quality_loss'
                      ? `${format(changeVariants.at(-1).value * 100)} percentage points allowed loss`
                      : `${changeVariants.at(-1).value} detour weight`}{' '}
                    versus baseline, matching trip, persona, stop count and seed. Only pairs with
                    assessed utility on both sides are included. This is not a significance test.
                  </ResearchInfo>
                </div>
              )}
            </section>
          )}
          <section className="research-card">
            <ChartHeading
              as="h2"
              title="Solver outcomes"
              help="Counts under the selected filters. OPTIMAL proves the best spacing-and-detour objective within the utility bound; it does not mean highest utility. FEASIBLE found a valid solution without proving it best within the time limit. INFEASIBLE means no solution meets the model constraints. UNKNOWN means no solution or proof was returned in time. A zero-loss bound can be unattainable due to score rounding; that does not establish a shortage of attractions."
            />
            <div className="research-statuses">
              {Object.entries(solverCounts).map(([label, count]) => (
                <div key={label}>
                  <span>{label.replaceAll('_', ' ')}</span>
                  <strong>{count}</strong>
                </div>
              ))}
              {!filtered.length && <p>No results yet.</p>}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
