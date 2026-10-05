import PropTypes from 'prop-types';
import { useEffect, useState } from 'react';
import { getLabRuns, labError } from '../../services/algorithmLab';
import HelpTip from './HelpTip';
import TripEvaluation from './TripEvaluation';
import SavedTripDialog from './SavedTripDialog';

export default function RunHistory({ revision }) {
  const [data, setData] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setData(null);
    getLabRuns(controller.signal, offset)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(labError(failure));
      });
    return () => controller.abort();
  }, [revision, offset, refresh]);
  return (
    <section className="lab-history" aria-label="Saved run history">
      {selectedRun && <SavedTripDialog run={selectedRun} onClose={() => setSelectedRun(null)} />}
      <div className="lab-actions">
        <h2>Run history</h2>
        <button type="button" onClick={() => setRefresh(refresh + 1)}>
          Refresh history
        </button>
        <HelpTip label="run measurements">
          Scores measure attraction selection, not the whole trip. Replay does not verify roads or
          hotels. Feasibility checks places, driving and the nightly room target; total-trip budget
          is not enforced. Repeated-input statistics use matching inputs and scoring versions;
          quality ratios additionally require identical candidates on this page only.
        </HelpTip>
      </div>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading history…</p>}
      {data && (
        <>
          <p className="lab-note">
            Saved separately from chats. Showing {data.runs.length} runs
            {offset ? ` from ${offset + 1}` : ''}.
          </p>
          {data.page_summary && (
            <p className="lab-note">
              Current page: {data.page_summary.completed} completed, {data.page_summary.failed}{' '}
              failed, {data.page_summary.unfinished} unfinished. Completion rate:{' '}
              {data.page_summary.completion_rate == null
                ? 'Unassessed'
                : `${(data.page_summary.completion_rate * 100).toFixed(1)}%`}{' '}
              ({data.page_summary.completion_assessed} finished runs assessed).
            </p>
          )}
          <div className="lab-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Experiment</th>
                  <th>Status</th>
                  <th>Selection score</th>
                  <th>Time</th>
                  <th>API attempts</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {data.runs.map((run) => {
                  const metrics = run.metrics;
                  const group = data.groups.find(
                    (item) =>
                      item.cohort_key === metrics?.cohort_key &&
                      (item.metric_version == null ||
                        item.metric_version === metrics?.metric_version) &&
                      (item.revision == null || item.revision === metrics?.revision)
                  );
                  return (
                    <tr key={run.id}>
                      <td>
                        {run.preset_id}
                        <small>
                          {run.mode} · {new Date(run.started_at).toLocaleString()}
                        </small>
                      </td>
                      <td>{run.status}</td>
                      <td>{metrics?.objective_score?.toLocaleString() ?? 'Unassessed'}</td>
                      <td>
                        {metrics
                          ? metrics.latency_ms.total < 1000
                            ? `${metrics.latency_ms.total.toFixed(1)} ms`
                            : `${(metrics.latency_ms.total / 1000).toFixed(2)} s`
                          : '—'}
                      </td>
                      <td>
                        {metrics
                          ? Object.values(metrics.external_calls).reduce(
                              (sum, value) => sum + value,
                              0
                            )
                          : '—'}
                      </td>
                      <td>
                        {run.has_result && (
                          <button type="button" onClick={() => setSelectedRun(run)}>
                            View map and itinerary
                          </button>
                        )}
                        <details>
                          <summary>Inspect</summary>
                          <p>
                            Nightly-target feasibility:{' '}
                            {metrics?.feasibility == null
                              ? 'Unassessed'
                              : metrics.feasibility
                                ? 'Pass'
                                : 'Fail'}
                          </p>
                          {group && (
                            <p>
                              {group.runs} comparable run(s). Same output:{' '}
                              {group.deterministic_observed == null
                                ? 'needs repeats'
                                : group.deterministic_observed
                                  ? 'yes'
                                  : 'no'}
                              . Mean score: {group.objective?.mean?.toFixed(2) ?? 'unavailable'};
                              standard deviation:{' '}
                              {group.objective?.stddev?.toFixed(2) ?? 'unavailable'}.
                            </p>
                          )}
                          <TripEvaluation metrics={metrics} />
                          {group?.trip_evaluation && (
                            <div aria-label="Current page trip statistics">
                              <p>
                                Matching runs on this page only. Mean ± population standard
                                deviation:
                              </p>
                              {Object.entries(group.trip_evaluation).map(([label, stats]) => (
                                <p key={label}>
                                  {label.replaceAll('_', ' ')}:{' '}
                                  {stats
                                    ? `${stats.mean.toFixed(2)} ± ${stats.stddev.toFixed(2)}; min ${stats.min.toFixed(2)}, max ${stats.max.toFixed(2)} (${stats.count} assessed)`
                                    : 'Unassessed'}
                                </p>
                              ))}
                            </div>
                          )}
                          <pre>
                            {JSON.stringify(
                              { input: run.input, metrics, comparison: group },
                              null,
                              2
                            )}
                          </pre>
                        </details>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="lab-actions">
            <button
              type="button"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Newer runs
            </button>
            <button
              type="button"
              disabled={data.next_offset == null}
              onClick={() => setOffset(data.next_offset)}
            >
              Older runs
            </button>
          </div>
        </>
      )}
    </section>
  );
}

RunHistory.propTypes = { revision: PropTypes.number.isRequired };
