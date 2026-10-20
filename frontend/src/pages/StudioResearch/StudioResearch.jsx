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
import { combineStudies, distribution, format, METRICS, paired, solverLabel } from './researchData';
import ResearchInfo, { ChartHeading } from './ResearchInfo';
import { InspectionProvider, InspectMark } from './ResearchInspect';
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
  const successful = trackRows.filter((row) => row.completed).length;
  const failed = trackRows.filter((row) => row.outcome === 'failed').length;
  const partial = trackRows.filter((row) => row.outcome === 'completed' && !row.completed).length;
  const interrupted = trackRows.filter((row) => row.outcome === 'interrupted').length;
  const percentFinished = (count) =>
    trackRows.length
      ? `${format((count / trackRows.length) * 100)}% of finished runs`
      : 'No finished runs yet';
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
    <InspectionProvider>
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
                Full trip planning · {data.counts.pipeline}
              </button>
              <button
                aria-pressed={track === 'solver'}
                onClick={() => {
                  setTrack('solver');
                  setMetric('utility_mean');
                }}
              >
                Stop selection · {data.counts.solver}
              </button>
            </nav>
            <div className="research-track-meta">
              <span>
                {track === 'pipeline'
                  ? 'Live trips'
                  : data.dataset_hashes.length === 1
                    ? '100 simulated attractions'
                    : 'Simulated attractions'}
              </span>
              <ResearchInfo label="Study data">
                {track === 'pipeline'
                  ? 'Complete live trips with valid timing. Hotel costs cover room-nights only.'
                  : 'Fixed simulated attractions and driving inputs. Repeated runs are not independent real-world samples.'}
              </ResearchInfo>
            </div>
            <div className="research-stat-row research-summary">
              <div>
                <span>Runs finished</span>
                <strong>{format(trackRows.length, 0)}</strong>
                <small>
                  {format(
                    (track === 'solver' ? data.counts.solver : data.counts.pipeline) -
                      trackRows.length,
                    0
                  )}{' '}
                  runs remaining
                </small>
              </div>
              <div>
                <span>Successful runs</span>
                <strong>{format(successful, 0)}</strong>
                <small>{percentFinished(successful)}</small>
              </div>
              <div>
                <span>Incomplete runs</span>
                <strong>{format(trackRows.length - successful, 0)}</strong>
                <small>
                  {failed} failed · {partial} partial · {interrupted} interrupted
                </small>
              </div>
              <InspectMark
                as="div"
                first
                disabled={!runtime.n}
                label="Observed planning time range"
                insight={{
                  value: `${format(runtime.min)}–${format(runtime.max)} sec range`,
                  detail: 'Includes timed failures',
                }}
              >
                <span>Typical planning time</span>
                <strong>
                  {format(runtime.median)}
                  <small> sec</small>
                </strong>
                <small>
                  {runtime.n > 1
                    ? `Middle half: ${format(runtime.q1)}–${format(runtime.q3)} sec`
                    : runtime.n === 1
                      ? '1 timed run'
                      : 'No times recorded'}
                </small>
              </InspectMark>
            </div>
            <div className="research-controls research-filters">
              <label>
                Measure
                <select value={metric} onChange={(e) => setMetric(e.target.value)}>
                  {Object.entries(METRICS)
                    .filter(([, value]) => track === 'pipeline' || !value.live)
                    .map(([key, value]) => (
                      <option value={key} key={key}>
                        {value.label}
                        {key === 'max_gap_seconds' && track === 'solver' ? ' (simulated)' : ''}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Interests
                <select value={persona} onChange={(e) => setPersona(e.target.value)}>
                  <option value="all">All interests</option>
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
                  Selection setting
                  <select value={variant} onChange={(e) => setVariant(e.target.value)}>
                    {data.variants.map((row) => (
                      <option value={row.id} key={row.id}>
                        {row.id === 'baseline'
                          ? 'Default settings'
                          : row.parameter === 'quality_loss'
                            ? `Allow ${format(row.value * 100)}-point utility score drop`
                            : `Extra driving penalty: ${row.value}×`}
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
                <Tradeoff rows={filtered} trips={trips} />
              </section>
            ) : (
              <section className="research-card">
                <ChartHeading
                  as="h2"
                  title="Settings comparison"
                  help="One setting changes; trip and stop count stay fixed. Interest and setting filters above do not apply."
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
                    <select
                      value={responseDensity}
                      onChange={(e) => setCurveDensity(e.target.value)}
                    >
                      {[1, 2, 3].map((n) => (
                        <option value={n} key={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Setting
                    <select value={parameter} onChange={(e) => setParameter(e.target.value)}>
                      <option value="quality_loss">Allowed utility score drop</option>
                      <option value="detour_weight">Extra driving penalty</option>
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
                    <div>
                      <strong>Average utility score change: {format(delta.mean)} points</strong>
                      <small>
                        {delta.n} matched run comparisons · observed change {format(delta.min)} to{' '}
                        {format(delta.max)} points
                      </small>
                    </div>
                    <ResearchInfo label="Average utility score change">
                      {parameter === 'quality_loss'
                        ? `${format(changeVariants.at(-1).value * 100)}-point allowed utility score drop`
                        : `${changeVariants.at(-1).value}× extra driving penalty`}{' '}
                      vs defaults. Same trip, interests, stop count and seed. Descriptive
                      comparison.
                    </ResearchInfo>
                  </div>
                )}
              </section>
            )}
            <section className="research-card">
              <ChartHeading
                as="h2"
                title="Selection results"
                help="Best proven: lowest spacing and driving cost within the utility score requirement. Strict zero-drop settings may fail from rounding."
              />
              <div className="research-statuses">
                {Object.entries(solverCounts).map(([label, count]) => (
                  <div key={label}>
                    <span>{solverLabel(label)}</span>
                    <strong>{format(count, 0)}</strong>
                    <small>{format((count / filtered.length) * 100)}% of filtered runs</small>
                  </div>
                ))}
                {!filtered.length && <p>No results yet.</p>}
              </div>
            </section>
          </>
        )}
      </main>
    </InspectionProvider>
  );
}
