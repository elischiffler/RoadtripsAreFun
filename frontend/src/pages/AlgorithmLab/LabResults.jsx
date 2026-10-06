import RunError from './RunError';
import PropTypes from 'prop-types';
import { useId, useState } from 'react';
import RouteOverview from './RouteOverview';
import ItineraryDays from '../../components/ItineraryDays';
import HelpTip from './HelpTip';
import TripEvaluation from './TripEvaluation';
import StageRunData from './StageRunData';

const numeric = (value, digits = 3) =>
  typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: digits })
    : 'Not available';
const words = (value) => value?.replaceAll('_', ' ');

export default function LabResults({ result, previous }) {
  const { explanation, route, itinerary } = result;
  const solver = explanation?.solver;
  const candidates = explanation?.candidates || [];
  const balanced = solver?.objective_direction === 'minimize';
  const [tab, setTab] = useState('route');
  const tabId = useId();
  const tabs = [
    ['route', 'Route'],
    ['itinerary', 'Itinerary'],
    ['details', 'Algorithm details'],
  ];
  const trip = result.run_record?.metrics?.trip_evaluation;
  const delivered =
    trip?.stop_fulfillment?.delivered ??
    (route
      ? route.stops?.filter((stop) => ['stop', 'attraction'].includes(stop.type)).length
      : null);
  const requested =
    trip?.stop_fulfillment?.requested ??
    solver?.requested_stops ??
    result.input_snapshot?.num_stops;
  const measure = (amount, divisor, unit) =>
    typeof amount === 'number' && Number.isFinite(amount)
      ? `${numeric(amount / divisor, 1)} ${unit}`
      : 'Not available';
  const warnings = [...new Set([...(route?.warnings || []), ...(trip?.warnings || [])])];
  const sameSnapshot =
    previous &&
    result.mode === 'replay' &&
    previous.mode === 'replay' &&
    previous.snapshot.id === result.snapshot.id;
  const selectedNames = (run) =>
    run.explanation?.candidates
      .filter((candidate) => candidate.selected)
      .map((candidate) => candidate.name)
      .join(', ') || 'None';
  return (
    <div className="lab-results">
      <div className={`lab-mode-banner ${result.mode === 'replay' ? 'lab-replay' : ''}`}>
        <strong>
          {result.mode === 'replay' ? 'Replay · frozen candidate fixture' : 'Live provider run'}
        </strong>
        <p>{result.snapshot.label}</p>
        <p className="lab-note">
          {result.mode === 'replay'
            ? 'Selection only · synthetic places · no live route'
            : 'Fresh discovery · scheduling and road checks follow selection'}
        </p>
        <details>
          <summary>Source and scope</summary>
          <p>{result.snapshot.source}</p>
          {result.mode === 'replay' && (
            <p>
              Uses the same scoring and selection pipeline on saved inputs. The solver status below
              shows whether a solve was performed. Only interests and the stop cap affect replay
              selection; dates, cities, rooms and car details do not change this frozen problem.
              Road routing, hotel availability and itinerary generation were not run.
            </p>
          )}
        </details>
      </div>
      <RunError error={result.error} attempts={result.attempts} />
      {result.stages
        .filter((stage) => stage.status === 'failed')
        .map((stage) => (
          <p key={stage.name} className="lab-warning">
            {words(stage.name)} failed: {stage.detail}
          </p>
        ))}
      {route && !itinerary?.length && (
        <p className="lab-warning">Route available; itinerary generation is incomplete.</p>
      )}
      {warnings.map((warning, index) => (
        <p key={index} className="lab-warning">
          {warning}
        </p>
      ))}
      <dl className="lab-summary" aria-label="Trip summary">
        <div>
          <dt>Distance</dt>
          <dd>{measure(route?.distance, 1609.344, 'miles')}</dd>
        </div>
        <div>
          <dt>Driving time</dt>
          <dd>{measure(route?.duration, 3600, 'hours')}</dd>
        </div>
        <div>
          <dt>Attractions delivered / requested</dt>
          <dd>
            {numeric(delivered, 0)} / {numeric(requested, 0)}
          </dd>
        </div>
        <div>
          <dt>Quoted hotel total</dt>
          <dd>
            {typeof route?.cost === 'number' && Number.isFinite(route.cost)
              ? `$${numeric(route.cost, 2)}`
              : 'Not available'}
          </dd>
        </div>
      </dl>
      <p className="lab-note">
        Driving time excludes visits and overnight stays. Hotel quotes are not a whole-trip budget.
      </p>
      <div className="lab-tabs" role="tablist" aria-label="Run results">
        {tabs.map(([key, label], index) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`${tabId}-${key}-tab`}
            aria-controls={`${tabId}-${key}-panel`}
            aria-selected={tab === key}
            tabIndex={tab === key ? 0 : -1}
            onClick={() => setTab(key)}
            onKeyDown={(event) => {
              const next =
                event.key === 'ArrowRight'
                  ? (index + 1) % tabs.length
                  : event.key === 'ArrowLeft'
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === 'Home'
                      ? 0
                      : event.key === 'End'
                        ? tabs.length - 1
                        : null;
              if (next == null) return;
              event.preventDefault();
              setTab(tabs[next][0]);
              document.getElementById(`${tabId}-${tabs[next][0]}-tab`).focus();
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${tabId}-route-panel`}
        aria-labelledby={`${tabId}-route-tab`}
        hidden={tab !== 'route'}
        tabIndex={0}
      >
        {tab === 'route' &&
          (route ? (
            <RouteOverview key={result.snapshot.id} route={route} />
          ) : (
            <p>
              {result.mode === 'replay'
                ? 'Selection-only replay: no road route or hotel schedule was generated.'
                : 'No completed road route is available. Review Algorithm details for stage data and errors.'}
            </p>
          ))}
      </div>
      <div
        role="tabpanel"
        id={`${tabId}-itinerary-panel`}
        aria-labelledby={`${tabId}-itinerary-tab`}
        hidden={tab !== 'itinerary'}
        tabIndex={0}
      >
        {tab === 'itinerary' &&
          (itinerary?.length ? (
            <div className="lab-itinerary">
              <ItineraryDays itinerary={itinerary} />
            </div>
          ) : (
            <p>No completed itinerary is available for this run.</p>
          ))}
      </div>
      <div
        role="tabpanel"
        id={`${tabId}-details-panel`}
        aria-labelledby={`${tabId}-details-tab`}
        hidden={tab !== 'details'}
        tabIndex={0}
        className="lab-diagnostics"
      >
        <StageRunData result={result} />
        {solver && (
          <section aria-labelledby="lab-solve-heading">
            <h2 id="lab-solve-heading">Attraction selection</h2>
            <div className="lab-solve-heading">
              <strong className="lab-solver-status">{solver.status}</strong>
              <HelpTip label="solver status">
                OPTIMAL proves the best modeled selection. FEASIBLE is valid without proof of
                optimality. NOT_RUN means no solve occurred.
              </HelpTip>
              <span>
                {solver.selected_count} selected / {solver.requested_stops} maximum ·{' '}
                {solver.eligible_count} eligible
              </span>
            </div>
            <p>
              {solver.status === 'OPTIMAL'
                ? 'The best modeled attraction objective was proved for this candidate set.'
                : solver.status === 'FEASIBLE'
                  ? 'A valid attraction selection was found. Optimality was not proved.'
                  : solver.status === 'NOT_RUN'
                    ? 'No solver run was performed. See the pipeline and candidate reasons.'
                    : 'The solver did not return a successful attraction selection.'}
            </p>
            <dl className="lab-metrics">
              <div>
                <dt>
                  {balanced ? 'Selection cost (seconds)' : 'Integer objective'}{' '}
                  <HelpTip label="integer objective">
                    {balanced
                      ? 'Minimized sum of all route-gap deviations and estimated solo detours, in seconds.'
                      : 'Historical maximized match surplus plus small tie preferences. It is not a percentage.'}
                  </HelpTip>
                </dt>
                <dd>{numeric(solver.objective_value, 0)}</dd>
              </div>
              <div>
                <dt>
                  Best bound{' '}
                  <HelpTip label="best bound">
                    {balanced
                      ? 'A lower bound on the minimum selection cost.'
                      : 'An upper limit on the historical maximized objective.'}{' '}
                    Matching the objective proves optimality for this model.
                  </HelpTip>
                </dt>
                <dd>{numeric(solver.best_bound, 0)}</dd>
              </div>
              <div>
                <dt>Solver time</dt>
                <dd>{numeric(solver.wall_time_seconds)} s</dd>
              </div>
              <div>
                <dt>
                  Utility threshold{' '}
                  <HelpTip label="utility threshold">
                    Candidates below this match score are excluded before solving.
                  </HelpTip>
                </dt>
                <dd>{numeric(solver.utility_threshold)}</dd>
              </div>
            </dl>
            {balanced && (
              <dl className="lab-metrics">
                <div>
                  <dt>Average match</dt>
                  <dd>{numeric(solver.average_match)}</dd>
                </div>
                <div>
                  <dt>Best achievable average</dt>
                  <dd>{numeric(solver.best_average_match)}</dd>
                </div>
                <div>
                  <dt>Quality loss</dt>
                  <dd>{numeric(solver.quality_loss * 100)} percentage points</dd>
                </div>
                <div>
                  <dt>Gap deviation</dt>
                  <dd>{numeric(solver.spacing_deviation_seconds / 60)} minutes</dd>
                </div>
                <div>
                  <dt>Estimated solo detours</dt>
                  <dd>{numeric(solver.estimated_detour_seconds / 60)} minutes</dd>
                </div>
              </dl>
            )}
            <details>
              <summary>Constraints and objective formula</summary>
              {balanced ? (
                <>
                  <p className="lab-note">
                    Select K = min(requested, eligible). Average match must be at least the best
                    achievable average minus 0.10. Each minute of gap deviation and detour has the
                    same cost.
                  </p>
                  <pre>
                    {
                      'sum(x[i]) = K\naverage match ≥ best average − 0.10\nminimize sum(abs(gap − baseline / (K + 1))) + sum(detour)\nGaps include origin-to-first and last-to-destination.'
                    }
                  </pre>
                  <p className="lab-note">
                    Candidates are ordered by measured route progress and provider ID. Final road
                    legs and the daily schedule receive separate validation.
                  </p>
                </>
              ) : (
                <>
                  <p className="lab-note">
                    At most one attraction per route slot, within the requested stop cap. The
                    objective rewards rounded match surplus with a small tie preference. Hotel cost
                    and drive time are checked in later stages.
                  </p>
                  <pre>
                    {
                      'x[i] ∈ {0, 1}\nsum(x[i]) ≤ requested stops\nsum(x[i] in a slot) ≤ 1\n\nq[i] = round((utility[i] − threshold) × 1,000,000)\nB = m × (m + 1)\nc[i] = q[i] × (B + 1) + m − i\nmaximize sum(c[i] × x[i])'
                    }
                  </pre>
                  <p className="lab-note">
                    m is the eligible candidate count. i is the zero-based index after sorting by
                    slot and provider ID. Coefficients and results above come from the backend.
                  </p>
                </>
              )}
            </details>
          </section>
        )}
        {explanation?.discovery && (
          <section aria-label="Discovery coverage">
            <h2>Discovery coverage</h2>
            <p>{explanation.discovery.coverage_note}</p>
            <p>
              {words(explanation.discovery.stop_reason)}. Sparse sections:{' '}
              {explanation.discovery.sparse_sections?.map((id) => id + 1).join(', ') || 'None'}.
            </p>
          </section>
        )}
        <section aria-labelledby="lab-match-heading">
          <h2 id="lab-match-heading">Candidate matches</h2>
          <p className="lab-note">
            Inspect a place to see its score.{' '}
            <HelpTip label="match utility">
              Match utility is the sum of trip weight × location rating. It models preference match,
              not probability of enjoyment.
            </HelpTip>
            <HelpTip label="route section">
              {balanced
                ? 'Sections divide baseline driving time. Discovery balances capacity across them; selection uses measured progress without a one-per-section constraint.'
                : 'Historical candidates share a slot when closest to the same sampled route point.'}
            </HelpTip>
          </p>
          {sameSnapshot && (
            <div className="lab-comparison">
              <strong>Same snapshot comparison</strong>
              <p>Previous selection: {selectedNames(previous)}</p>
              <p>Current selection: {selectedNames(result)}</p>
              <details>
                <summary>Compare effective trip weights</summary>
                <div className="lab-table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Interest</th>
                        <th>Previous</th>
                        <th>Current</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(explanation?.weights || {}).map(([key, weight]) => (
                        <tr key={key}>
                          <th>{words(key)}</th>
                          <td>{numeric(previous.explanation?.weights?.[key])}</td>
                          <td>{numeric(weight)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          )}
          <details>
            <summary>Effective normalized trip weights</summary>
            <dl className="lab-weights">
              {Object.entries(explanation?.weights || {}).map(([key, value]) => (
                <div key={key}>
                  <dt>{words(key)}</dt>
                  <dd>{numeric(value, 5)}</dd>
                </div>
              ))}
            </dl>
          </details>
          <details>
            <summary>How location ratings are sourced</summary>
            <p className="lab-note">
              {result.mode === 'replay'
                ? 'This teaching fixture uses synthetic places and ratings. No provider verification was performed during replay.'
                : 'Provider checks establish identity and coordinates. Interest ratings are AI estimates.'}{' '}
              Inspect each candidate’s provenance below.
            </p>
          </details>
          {candidates.length === 0 && <p>No candidate diagnostics are available for this run.</p>}
          {candidates.map((candidate, index) => (
            <details
              key={`${candidate.provider_id ?? 'invalid'}-${index}`}
              className="lab-candidate"
            >
              <summary>
                <span>
                  <strong>{candidate.name}</strong>
                  <span className="lab-candidate-meta">
                    {candidate.selected ? 'Selected' : words(candidate.reason)} ·{' '}
                    {balanced ? 'section' : 'slot'}{' '}
                    {(balanced
                      ? candidate.section_id == null
                        ? null
                        : candidate.section_id + 1
                      : candidate.slot) ?? 'unassigned'}
                  </span>
                </span>
                <span className="lab-utility">{numeric(candidate.utility)}</span>
              </summary>
              <p>
                Selection reason: {words(candidate.reason)}.{' '}
                {balanced
                  ? `Route progress: ${numeric(candidate.route_progress_seconds / 60)} minutes; solo detour: ${numeric(candidate.detour_seconds / 60)} minutes.`
                  : `Integer coefficient: ${numeric(candidate.objective_coefficient, 0)}.`}
              </p>
              <div className="lab-table-scroll">
                <table>
                  <caption>Score contributions for {candidate.name}</caption>
                  <thead>
                    <tr>
                      <th>Interest</th>
                      <th>Trip weight</th>
                      <th>Place rating</th>
                      <th>Contribution</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(candidate.contributions || []).map((part) => (
                      <tr key={part.attribute}>
                        <th>{words(part.attribute)}</th>
                        <td>{numeric(part.weight, 5)}</td>
                        <td>{numeric(part.rating, 5)}</td>
                        <td>{numeric(part.contribution, 5)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="lab-note">Provider ID: {candidate.provider_id}</p>
              <pre>{JSON.stringify(candidate.provenance, null, 2)}</pre>
            </details>
          ))}
        </section>
        <TripEvaluation metrics={result.run_record?.metrics} />
        <details>
          <summary>Validated input snapshot</summary>
          <p className="lab-note">Values returned by the backend for this run.</p>
          <pre>{JSON.stringify(result.input_snapshot, null, 2)}</pre>
        </details>
      </div>
    </div>
  );
}

LabResults.propTypes = { result: PropTypes.object.isRequired, previous: PropTypes.object };
