import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
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
import { combineStudies, distribution, format, METRICS, paired } from './researchData';
import ResearchInfo, { ChartHeading } from './ResearchInfo';
import '../AlgorithmLab/AlgorithmLab.css';
import './StudioResearch.css';

export default function StudioResearch() {
  const [catalog, setCatalog] = useState(null);
  const [studies] = useState(savedStudies);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [busy, setBusy] = useState(false);
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
      .then(setCatalog)
      .catch((e) => {
        if (e.name !== 'CanceledError') setError('Chart labels are unavailable.');
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!studies.length) return;
    const controller = new AbortController();
    const snapshots = new Map();
    const observations = new Map(studies.map((study) => [study.id, new Map()]));
    let timer;
    const poll = async () => {
      const results = await Promise.allSettled(
        studies.map(async (study) => {
          const previous = snapshots.get(study.id);
          if (previous?.state === 'complete') return;
          const next = await studyRequest(
            study,
            '',
            'get',
            controller.signal,
            previous?.cursor ?? 0
          );
          if (controller.signal.aborted) return;
          const rows = observations.get(study.id);
          next.rows.forEach((row) => rows.set(row.id, row));
          snapshots.set(study.id, { ...next, id: study.id, rows: [...rows.values()] });
        })
      );
      if (controller.signal.aborted) return;
      const available = studies.map((study) => snapshots.get(study.id)).filter(Boolean);
      setData(combineStudies(available));
      setConnectionError(
        results.some((result) => result.status === 'rejected')
          ? 'Some results are unavailable. Retrying…'
          : ''
      );
      if (
        available.length !== studies.length ||
        available.some((value) => value.state !== 'complete')
      )
        timer = setTimeout(poll, 5000);
    };
    poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [studies]);

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
  const activeSources = (data?.sources ?? []).filter((source) =>
    ['running', 'starting', 'pausing'].includes(source.state)
  );
  const running = activeSources.length > 0;
  const nextSource = data?.sources.find((source) => source.state !== 'complete');

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
      <div className="research-toolbar">
        {data && (
          <>
            <span className="research-state" role="status">
              {data.state} · {format(finished, 0)} / {format(data.counts.total, 0)}
            </span>
            {running ? (
              <button
                disabled={busy || activeSources.every((source) => source.state === 'pausing')}
                onClick={() =>
                  action(() =>
                    Promise.all(
                      activeSources.map((source) =>
                        studyRequest(
                          studies.find((study) => study.id === source.id),
                          'pause',
                          'post'
                        )
                      )
                    )
                  )
                }
              >
                Pause
              </button>
            ) : (
              nextSource && (
                <button
                  disabled={busy}
                  onClick={() =>
                    action(() =>
                      studyRequest(
                        studies.find((study) => study.id === nextSource.id),
                        'start',
                        'post'
                      )
                    )
                  }
                >
                  Resume
                </button>
              )
            )}
            <button
              aria-label="Export CSV"
              onClick={() => action(() => downloadStudy(studies, 'csv'))}
              disabled={busy}
            >
              CSV
            </button>
            <button
              aria-label="Export JSON"
              onClick={() => action(() => downloadStudy(studies, 'json'))}
              disabled={busy}
            >
              JSON
            </button>
          </>
        )}
      </div>
      {!data ? (
        <p className="research-empty">{studies.length ? 'Loading…' : 'No results yet.'}</p>
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
                : data.dataset_hashes.length === 1
                  ? '100 synthetic candidates'
                  : 'Synthetic candidates'}
            </span>
            <ResearchInfo label="Study data">
              {track === 'pipeline'
                ? 'Fresh live trips through the complete pipeline. Quality scores require fully delivered, timing-valid itineraries. Hotel metrics cover quoted room-nights only, not the total trip budget. Missing quotes are unassessed.'
                : 'Controlled trials on fixed synthetic candidates. Gap and detour inputs are simulated, not measured journeys. Saved runs are combined here and may reuse solver seeds; they are not independent real-world samples. The baseline allows 10 percentage points of utility loss, spacing weight 1, detour weight 1, a five-second limit and one worker.'}{' '}
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
