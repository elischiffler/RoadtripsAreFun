import PropTypes from 'prop-types';
import Map from '../../components/Map';
import ItineraryDays from '../../components/ItineraryDays';
import HelpTip from './HelpTip';
import TripEvaluation from './TripEvaluation';

const numeric = (value, digits = 3) =>
  typeof value === 'number'
    ? value.toLocaleString(undefined, { maximumFractionDigits: digits })
    : 'Not available';
const words = (value) => value?.replaceAll('_', ' ');

export default function LabResults({ result, previous }) {
  const { explanation, route, itinerary } = result;
  const solver = explanation?.solver;
  const candidates = explanation?.candidates || [];
  const geometry = route?.geometry?.coordinates;
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
      {result.error && (
        <p role="alert" className="lab-error">
          {result.error.message} ({result.error.code})
        </p>
      )}
      <section aria-labelledby="lab-stage-heading">
        <h2 id="lab-stage-heading">Pipeline outcomes</h2>
        <p className="lab-note">Each stage reports its own result.</p>
        <ol className="lab-stages">
          {result.stages.map((stage) => (
            <li key={stage.name}>
              <div>
                <strong>{words(stage.name)}</strong>
                <span className={`lab-status lab-status-${stage.status}`}>
                  {words(stage.status)}
                </span>
              </div>
              <details>
                <summary>Stage details</summary>
                <p>{stage.detail}</p>
              </details>
            </li>
          ))}
        </ol>
      </section>
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
                Integer objective{' '}
                <HelpTip label="integer objective">
                  The solver’s maximized integer score: rounded match surplus plus small tie
                  preferences. It is not a percentage.
                </HelpTip>
              </dt>
              <dd>{numeric(solver.objective_value, 0)}</dd>
            </div>
            <div>
              <dt>
                Best bound{' '}
                <HelpTip label="best bound">
                  An upper limit on the best possible objective. Matching the objective proves
                  optimality for this model.
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
          <details>
            <summary>Constraints and objective formula</summary>
            <p className="lab-note">
              At most one attraction per route slot, within the requested stop cap. The objective
              rewards rounded match surplus with a small tie preference. Hotel cost and drive time
              are checked in later stages.
            </p>
            <pre>
              {
                'x[i] ∈ {0, 1}\nsum(x[i]) ≤ requested stops\nsum(x[i] in a slot) ≤ 1\n\nq[i] = round((utility[i] − threshold) × 1,000,000)\nB = m × (m + 1)\nc[i] = q[i] × (B + 1) + m − i\nmaximize sum(c[i] × x[i])'
              }
            </pre>
            <p className="lab-note">
              m is the eligible candidate count. i is the zero-based index after sorting by slot and
              provider ID. Coefficients and results above come from the backend.
            </p>
          </details>
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
          <HelpTip label="route slot">
            Candidates share a slot when they are closest to the same sampled route point. The
            solver can select at most one per slot.
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
          <details key={`${candidate.provider_id ?? 'invalid'}-${index}`} className="lab-candidate">
            <summary>
              <span>
                <strong>{candidate.name}</strong>
                <span className="lab-candidate-meta">
                  {candidate.selected ? 'Selected' : words(candidate.reason)} · slot{' '}
                  {candidate.slot ?? 'unassigned'}
                </span>
              </span>
              <span className="lab-utility">{numeric(candidate.utility)}</span>
            </summary>
            <p>
              Selection reason: {words(candidate.reason)}. Integer coefficient:{' '}
              {numeric(candidate.objective_coefficient, 0)}.
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
      <section aria-labelledby="lab-route-heading">
        <h2 id="lab-route-heading">Route and itinerary</h2>
        {route ? (
          <>
            <p>
              {numeric(route.distance / 1609.344, 1)} miles · {numeric(route.duration / 3600, 1)}{' '}
              hours driving · ${numeric(route.cost, 2)} hotel quotes
            </p>
            <p className="lab-note">
              Driving time excludes visits and overnight stays. Hotel quotes are not a whole-trip
              budget.
            </p>
            {geometry?.length > 1 && (
              <div className="lab-map">
                <Map
                  key={result.snapshot.id}
                  UserChatData={{
                    route,
                    startConfirmed: { longitude: geometry[0][0], latitude: geometry[0][1] },
                    endConfirmed: { longitude: geometry.at(-1)[0], latitude: geometry.at(-1)[1] },
                  }}
                />
              </div>
            )}
            {route.warnings?.map((warning, index) => (
              <p key={index} className="lab-warning">
                {warning}
              </p>
            ))}
            <ol className="lab-route-stops">
              {route.stops?.map((stop, index) => (
                <li key={index}>
                  {stop.name} {stop.type && <span>({stop.type})</span>}
                </li>
              ))}
            </ol>
          </>
        ) : (
          <p>
            {result.mode === 'replay'
              ? 'Selection-only replay: no road route or hotel schedule was generated.'
              : 'No completed road route is available. Review the pipeline outcomes above.'}
          </p>
        )}
        {itinerary ? (
          <div className="lab-itinerary">
            <ItineraryDays itinerary={itinerary} />
          </div>
        ) : (
          route && <p>Route available; itinerary generation is incomplete.</p>
        )}
      </section>
      <TripEvaluation metrics={result.run_record?.metrics} />
      <details>
        <summary>Validated input snapshot</summary>
        <p className="lab-note">Values returned by the backend for this run.</p>
        <pre>{JSON.stringify(result.input_snapshot, null, 2)}</pre>
      </details>
    </div>
  );
}

LabResults.propTypes = { result: PropTypes.object.isRequired, previous: PropTypes.object };
