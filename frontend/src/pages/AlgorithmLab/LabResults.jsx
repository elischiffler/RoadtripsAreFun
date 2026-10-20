import RunError from './RunError';
import PropTypes from 'prop-types';
import { useId, useState } from 'react';
import RouteOverview from './RouteOverview';
import ItineraryDays from '../../components/ItineraryDays';
import TripStats from './TripStats';

const numeric = (value, digits = 3) =>
  typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: digits })
    : 'Not available';
const words = (value) => value?.replaceAll('_', ' ');

export default function LabResults({ result }) {
  const { explanation, route, itinerary } = result;
  const solver = explanation?.solver;
  const [tab, setTab] = useState('route');
  const tabId = useId();
  const tabs = [
    ['route', 'Route'],
    ['itinerary', 'Itinerary'],
    ['details', 'Trip stats'],
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
                : 'No completed road route is available.'}
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
        <TripStats result={result} />
      </div>
    </div>
  );
}

LabResults.propTypes = { result: PropTypes.object.isRequired };
