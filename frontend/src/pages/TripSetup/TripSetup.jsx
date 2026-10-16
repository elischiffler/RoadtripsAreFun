import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import useSetupDraft from './useSetupDraft';
import {
  INTERESTS,
  PLACES,
  PLACE_REASONS,
  MAX_SETUP_ROOMS,
  STEPS,
  newSetupDraft,
  preferenceWeights,
  setupErrors,
  setupMessage,
  setupSummary,
  weightsAcknowledged,
} from './setupModel';
import PreferenceProfile from './PreferenceProfile';
import './TripSetup.css';

export default function TripSetup({ onSubmit, onContinue, busy = false }) {
  const { draft, setDraft, step, setStep, stored, reset } = useSetupDraft();
  const [errors, setErrors] = useState({});
  const [receipt, setReceipt] = useState(null);
  const [sending, setSending] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [visited, setVisited] = useState(step);
  const heading = useRef(null);
  const errorSummary = useRef(null);
  const alive = useRef(true);
  const previousStep = useRef(step);
  const locked = busy || sending;
  let weights;
  let weightsValid = true;
  try {
    weights = preferenceWeights(draft);
  } catch {
    weights = preferenceWeights(newSetupDraft());
    weightsValid = false;
  }

  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    if (previousStep.current !== step)
      heading.current?.scrollIntoView({ block: 'start', behavior: 'instant' });
    previousStep.current = step;
  }, [step]);
  useEffect(() => {
    if (Object.keys(errors).length) errorSummary.current?.focus();
  }, [errors]);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const set = (key, value) => {
    setDraft((old) => ({ ...old, [key]: value }));
    setErrors({});
    setReceipt(null);
  };
  const go = (next) => {
    setErrors({});
    setVisited((previous) => Math.max(previous, next));
    setStep(next);
  };
  const next = () => {
    const issues = setupErrors(draft, step);
    if (Object.keys(issues).length) setErrors(issues);
    else go(step + 1);
  };
  const send = async (event) => {
    event.preventDefault();
    if (locked) return;
    if (step < 4) {
      next();
      return;
    }
    for (let index = 0; index < 4; index++) {
      const issues = setupErrors(draft, index);
      if (Object.keys(issues).length) {
        setStep(index);
        setErrors(issues);
        return;
      }
    }
    setSending(true);
    setReceipt(null);
    try {
      const result = await onSubmit({
        message: setupMessage(draft),
        displayText: setupSummary(draft),
      });
      if (!alive.current) return;
      setReceipt({ ...result, confirmed: weightsAcknowledged(result, preferenceWeights(draft)) });
    } catch {
      if (alive.current) setReceipt({ confirmed: false });
    } finally {
      if (alive.current) setSending(false);
    }
  };
  const field = (key, label, type = 'text', extra = {}) => (
    <div className="setup-field">
      <label htmlFor={'setup-' + key}>{label}</label>
      <input
        id={'setup-' + key}
        type={type}
        value={draft[key]}
        onChange={(event) => set(key, event.target.value)}
        aria-invalid={!!errors[key]}
        aria-describedby={errors[key] ? 'setup-' + key + '-error' : undefined}
        {...extra}
      />
      {errors[key] && (
        <small id={'setup-' + key + '-error'} className="setup-error">
          {errors[key]}
        </small>
      )}
    </div>
  );
  const updateRoom = (index, key, value) =>
    set(
      'rooms',
      draft.rooms.map((room, i) => (i === index ? { ...room, [key]: value } : room))
    );
  const toggleInterest = (key) => {
    setDraft((old) => ({
      ...old,
      customWeights: null,
      interests: old.interests.includes(key)
        ? old.interests.filter((k) => k !== key)
        : [...old.interests, key],
    }));
    setReceipt(null);
    setErrors({});
  };
  const answerPlace = (id, answer) => {
    setDraft((old) => ({ ...old, customWeights: null, ratings: { ...old.ratings, [id]: answer } }));
    setReceipt(null);
    setErrors({});
  };

  return (
    <main className="trip-setup">
      <div className="setup-wayfinding">
        <Link to="/">Home</Link>
        <span>Plan a trip</span>
        <Link to="/chat">Saved trips</Link>
        <Link to="/studio">AI Studio</Link>
      </div>
      <header className="setup-intro">
        <p className="setup-eyebrow">A road trip, your way</p>
        <h1>Make room for the good stops.</h1>
        <p>A few details, a little inspiration. We’ll help you shape the trip.</p>
      </header>
      <div className="setup-card">
        <nav aria-label="Trip setup progress" className="setup-progress">
          <p>
            Step {step + 1} of {STEPS.length} <span>{STEPS[step]}</span>
          </p>
          <ol>
            {STEPS.map((name, index) => (
              <li key={name}>
                <button
                  type="button"
                  aria-current={index === step ? 'step' : undefined}
                  disabled={locked || index > visited}
                  onClick={() => go(index)}
                  aria-label={'Step ' + (index + 1) + ': ' + name}
                >
                  <span aria-hidden="true">{index < step ? '✓' : index + 1}</span>
                  <span className="setup-step-name">{name}</span>
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <form onSubmit={send} noValidate aria-busy={locked}>
          <div className="setup-section" key={step}>
            <h2 ref={heading} tabIndex={-1}>
              {STEPS[step]}
            </h2>
            {Object.keys(errors).length > 0 && (
              <div ref={errorSummary} tabIndex={-1} role="alert" className="setup-error-summary">
                <p>Please check these details.</p>
                <ul>
                  {Object.entries(errors).map(([key, value]) => (
                    <li key={key}>
                      <a href={'#setup-' + key}>{value}</a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <fieldset disabled={locked} className="setup-fields">
              <legend className="setup-visually-hidden">{STEPS[step]} details</legend>
              {step === 0 && (
                <>
                  <p>Where are you heading?</p>
                  {field('start', 'Starting city or address', 'text', {
                    autoComplete: 'off',
                    maxLength: 256,
                  })}
                  {field('destination', 'Destination', 'text', {
                    autoComplete: 'off',
                    maxLength: 256,
                  })}
                  <div className="setup-grid">
                    {field('date', 'Departure date', 'date')}
                    {field('time', 'Departure time', 'time')}
                  </div>
                  <p className="setup-hint">
                    Times use your starting location. You’ll confirm suggested addresses before
                    planning.
                  </p>
                  {field('stops', 'How many attractions would you like?', 'number', {
                    min: 1,
                    step: 1,
                    inputMode: 'numeric',
                  })}
                </>
              )}
              {step === 1 && (
                <>
                  <p>Who’s coming along?</p>
                  {field('travelers', 'Total people, including you', 'number', {
                    min: 1,
                    step: 1,
                    inputMode: 'numeric',
                  })}
                  <div
                    id="setup-rooms"
                    tabIndex={-1}
                    aria-describedby={errors.rooms ? 'setup-rooms-error' : undefined}
                  >
                    {draft.rooms.map((room, index) => (
                      <fieldset className="setup-room" key={index}>
                        <legend>Room {index + 1}</legend>
                        <div className="setup-grid">
                          <label className="setup-field">
                            Adults
                            <input
                              type="number"
                              min="1"
                              step="1"
                              value={room.adults}
                              onChange={(e) => updateRoom(index, 'adults', e.target.value)}
                            />
                          </label>
                          <label className="setup-field">
                            Child ages, if any
                            <input
                              placeholder="For example, 5, 8"
                              value={room.children}
                              onChange={(e) => updateRoom(index, 'children', e.target.value)}
                            />
                          </label>
                        </div>
                        {draft.rooms.length > 1 && (
                          <button
                            type="button"
                            className="setup-text-button"
                            onClick={() =>
                              set(
                                'rooms',
                                draft.rooms.filter((_, i) => i !== index)
                              )
                            }
                          >
                            Remove room {index + 1}
                          </button>
                        )}
                      </fieldset>
                    ))}
                    {errors.rooms && (
                      <p id="setup-rooms-error" className="setup-error">
                        {errors.rooms}
                      </p>
                    )}
                    <button
                      type="button"
                      className="setup-secondary"
                      disabled={draft.rooms.length >= MAX_SETUP_ROOMS}
                      onClick={() => set('rooms', [...draft.rooms, { adults: '1', children: '' }])}
                    >
                      Add a room
                    </button>
                  </div>
                  {field('budget', 'Hotel target per room, per night (USD)', 'number', {
                    min: 0,
                    step: 'any',
                    inputMode: 'decimal',
                  })}
                  <p className="setup-hint">
                    A nightly target, not a total-trip budget. Food, fuel and tickets aren’t
                    included. Current hotel quotes appear after planning.
                  </p>
                </>
              )}
              {step === 2 && (
                <>
                  <p>What would make this trip enjoyable? Choose any, or keep a balanced mix.</p>
                  <div className="setup-interest-grid" id="setup-interests">
                    {Object.entries(INTERESTS).map(([key, label]) => (
                      <label
                        className={
                          'setup-choice ' + (draft.interests.includes(key) ? 'is-selected' : '')
                        }
                        key={key}
                      >
                        <input
                          type="checkbox"
                          checked={draft.interests.includes(key)}
                          onChange={() => toggleInterest(key)}
                        />
                        <span>{label}</span>
                      </label>
                    ))}
                  </div>
                  <h3>A little inspiration</h3>
                  <p>
                    How interested would you be in visiting these real places? You don’t need to
                    have been there.
                  </p>
                  {PLACES.map((place) => {
                    const answer = draft.ratings[place.id] ?? { rating: null, reasons: [] };
                    return (
                      <article className="setup-place" key={place.id}>
                        <p className="setup-eyebrow">Boulder, Colorado</p>
                        <h4>{place.name}</h4>
                        <p>{place.description}</p>
                        <a href={place.url} target="_blank" rel="noreferrer">
                          Read the operator’s visitor information
                          <span className="setup-visually-hidden"> for {place.name} (new tab)</span>
                        </a>
                        <fieldset className="setup-rating">
                          <legend>Your interest in {place.name}</legend>
                          {[
                            [1, 'Not for me'],
                            [3, 'Maybe'],
                            [5, 'Very interested'],
                          ].map(([rating, label]) => (
                            <label key={rating}>
                              <input
                                type="radio"
                                name={place.id}
                                value={rating}
                                checked={answer.rating === rating}
                                onChange={() =>
                                  answerPlace(place.id, { ...answer, rating, skipped: false })
                                }
                              />
                              {label}
                            </label>
                          ))}
                        </fieldset>
                        {answer.rating !== null && (
                          <fieldset className="setup-rating">
                            <legend>Which parts explain your answer?</legend>
                            {PLACE_REASONS.map((key) => (
                              <label key={key}>
                                <input
                                  type="checkbox"
                                  checked={answer.reasons.includes(key)}
                                  onChange={() =>
                                    answerPlace(place.id, {
                                      ...answer,
                                      reasons: answer.reasons.includes(key)
                                        ? answer.reasons.filter((k) => k !== key)
                                        : [...answer.reasons, key],
                                    })
                                  }
                                />
                                {INTERESTS[key]}
                              </label>
                            ))}
                          </fieldset>
                        )}
                        <div className="setup-inline-actions">
                          <button
                            type="button"
                            className="setup-text-button"
                            onClick={() =>
                              answerPlace(place.id, { rating: null, reasons: [], skipped: true })
                            }
                          >
                            Skip<span className="setup-visually-hidden"> {place.name}</span>
                          </button>
                          <button
                            type="button"
                            className="setup-text-button"
                            onClick={() =>
                              answerPlace(place.id, { rating: null, reasons: [], skipped: false })
                            }
                          >
                            Not sure
                            <span className="setup-visually-hidden"> about {place.name}</span>
                          </button>
                          <span aria-live="polite">
                            {answer.rating === null
                              ? answer.skipped
                                ? 'Skipped'
                                : 'No rating'
                              : 'Answer saved in draft'}
                          </span>
                        </div>
                      </article>
                    );
                  })}
                  <p className="setup-hint">
                    Place facts: City of Boulder Open Space and Mountain Parks, CC0 1.0, via the
                    reviewed catalog. Visitor evidence checked October 14, 2026; access can change.
                    These are your interest ratings, not public reviews.
                  </p>
                  <details className="setup-explanation">
                    <summary>How your answers shape the trip</summary>
                    <p>
                      Chosen interests start with four points; the others start with one. A place
                      answer adds or removes up to half a point for only the reasons you select.
                      Skipped or unsure answers change nothing. We turn the points into the shares
                      below, which the planner uses to match stops. This is an editable suggestion,
                      not a personality test.
                    </p>
                  </details>
                  {weightsValid ? (
                    <PreferenceProfile weights={weights} />
                  ) : (
                    <p role="status">
                      Give at least one interest an amount above zero to see your profile.
                    </p>
                  )}
                  <details className="setup-explanation">
                    <summary>Edit interest amounts</summary>
                    <p>
                      Use any non-negative amounts. At least one must be above zero. New question
                      answers replace these manual edits.
                    </p>
                    <div className="setup-grid">
                      {Object.entries(INTERESTS).map(([key, label]) => (
                        <label className="setup-field" key={key}>
                          {label}
                          <input
                            type="number"
                            min="0"
                            step="any"
                            value={
                              draft.customWeights?.[key] ?? Number((weights[key] * 100).toFixed(3))
                            }
                            onChange={(e) =>
                              set('customWeights', {
                                ...(draft.customWeights ??
                                  Object.fromEntries(
                                    Object.entries(weights).map(([k, v]) => [
                                      k,
                                      Number((v * 100).toFixed(3)),
                                    ])
                                  )),
                                [key]: e.target.value === '' ? 0 : Number(e.target.value),
                              })
                            }
                          />
                        </label>
                      ))}
                    </div>
                  </details>
                  {errors.interests && <p className="setup-error">{errors.interests}</p>}
                  <button
                    type="button"
                    className="setup-text-button"
                    onClick={() => {
                      setDraft((old) => ({
                        ...old,
                        interests: [],
                        ratings: {},
                        customWeights: null,
                      }));
                      setReceipt(null);
                      setErrors({});
                    }}
                  >
                    Reset interests
                  </button>
                  <button
                    type="button"
                    className="setup-text-button"
                    onClick={() => {
                      setDraft((old) => ({
                        ...old,
                        interests: [],
                        ratings: {},
                        customWeights: null,
                      }));
                      go(3);
                    }}
                  >
                    Skip interests and use a balanced mix
                  </button>
                </>
              )}
              {step === 3 && (
                <>
                  <p>Set a comfortable rhythm for your days.</p>
                  <label className="setup-field" htmlFor="setup-carStatus">
                    Would you like to add your car?
                    <select
                      id="setup-carStatus"
                      value={draft.carStatus}
                      onChange={(e) => set('carStatus', e.target.value)}
                      aria-invalid={!!errors.carStatus}
                    >
                      <option value="unanswered">Choose an option</option>
                      <option value="skipped">Skip car details</option>
                      <option value="provided">Add my car</option>
                    </select>
                    {errors.carStatus && <small className="setup-error">{errors.carStatus}</small>}
                  </label>
                  {draft.carStatus === 'provided' && (
                    <div className="setup-grid">
                      {field('year', 'Car year', 'number')}
                      {field('make', 'Car make')}
                      {field('model', 'Car model')}
                    </div>
                  )}
                  <div className="setup-grid" id="setup-schedule" tabIndex={-1}>
                    {[
                      ['preferred_hotel_arrival', 'Preferred hotel arrival'],
                      ['latest_hotel_arrival', 'Latest hotel arrival'],
                      ['latest_destination_arrival', 'Latest destination arrival'],
                      ['morning_restart', 'Start driving next morning'],
                    ].map(([key, label]) => (
                      <label className="setup-field" key={key}>
                        {label}
                        <input
                          type="time"
                          value={draft.schedule[key]}
                          onChange={(e) =>
                            set('schedule', { ...draft.schedule, [key]: e.target.value })
                          }
                        />
                      </label>
                    ))}
                  </div>
                  <label className="setup-choice">
                    <input
                      type="checkbox"
                      checked={draft.schedule.late_driving}
                      onChange={(e) =>
                        set('schedule', { ...draft.schedule, late_driving: e.target.checked })
                      }
                    />
                    Allow driving later into the evening
                  </label>
                  {draft.schedule.late_driving && (
                    <label className="setup-field">
                      Stop late driving by (24:00 means midnight)
                      <input
                        value={draft.schedule.late_cutoff}
                        onChange={(e) =>
                          set('schedule', { ...draft.schedule, late_cutoff: e.target.value })
                        }
                      />
                    </label>
                  )}
                  {errors.schedule && <p className="setup-error">{errors.schedule}</p>}
                  <p className="setup-hint">
                    Daily times are local to each stop. The planning service checks the final
                    schedule.
                  </p>
                </>
              )}
              {step === 4 && (
                <>
                  <p>Take a moment to check your answers. Nothing is sent until you continue.</p>
                  <div className="setup-review">
                    {[
                      [
                        'Where and when',
                        draft.start + ' → ' + draft.destination,
                        draft.date + ' at ' + draft.time + ' · ' + draft.stops + ' attractions',
                      ],
                      [
                        'People and rooms',
                        draft.travelers +
                          (Number(draft.travelers) === 1 ? ' person · ' : ' people · ') +
                          draft.rooms.length +
                          (draft.rooms.length === 1 ? ' room' : ' rooms'),
                        '$' +
                          draft.budget +
                          ' hotel target / room / night\n' +
                          draft.rooms
                            .map(
                              (room, index) =>
                                'Room ' +
                                (index + 1) +
                                ': ' +
                                room.adults +
                                (Number(room.adults) === 1 ? ' adult' : ' adults') +
                                (room.children.trim()
                                  ? '; child ages ' + room.children
                                  : '; no children')
                            )
                            .join('\n'),
                      ],
                      [
                        'What you enjoy',
                        Math.max(...Object.values(weights)) - Math.min(...Object.values(weights)) <
                        1e-10
                          ? 'A balanced mix across all interests'
                          : Object.entries(weights)
                              .sort((a, b) => b[1] - a[1])
                              .slice(0, 3)
                              .map(([key]) => INTERESTS[key])
                              .join(', '),
                        'Trip-only interests; account preferences stay separate',
                      ],
                      [
                        'Car and timing',
                        draft.carStatus === 'provided'
                          ? [draft.year, draft.make, draft.model].join(' ')
                          : 'Car details skipped',
                        'Hotel: prefer ' +
                          draft.schedule.preferred_hotel_arrival +
                          ', latest ' +
                          draft.schedule.latest_hotel_arrival +
                          '\nDestination by ' +
                          draft.schedule.latest_destination_arrival +
                          ' · next morning ' +
                          draft.schedule.morning_restart +
                          '\n' +
                          (draft.schedule.late_driving
                            ? 'Late driving allowed until ' + draft.schedule.late_cutoff
                            : 'Late driving not requested'),
                      ],
                    ].map(([title, primary, secondary], index) => (
                      <section key={title}>
                        <div>
                          <h3>{title}</h3>
                          <p>{primary}</p>
                          <p className="setup-hint">{secondary}</p>
                        </div>
                        <button
                          type="button"
                          className="setup-text-button"
                          onClick={() => go(index)}
                        >
                          Edit<span className="setup-visually-hidden"> {title}</span>
                        </button>
                      </section>
                    ))}
                  </div>
                  {weightsValid ? (
                    <PreferenceProfile weights={weights} label="Interests to send" />
                  ) : (
                    <p role="status">Fix the interest amounts before sending.</p>
                  )}
                  <p className="setup-hint">
                    We’ll ask the planning service to save these details for this trip. You’ll
                    confirm the suggested locations in chat before planning. Prices and travel-time
                    estimates arrive with the route.
                  </p>
                </>
              )}
            </fieldset>
            {receipt && (
              <div
                className={receipt.confirmed ? 'setup-confirmation' : 'setup-error-summary'}
                role={receipt.confirmed ? 'status' : 'alert'}
              >
                <h3>
                  {receipt.confirmed
                    ? 'Your interests are confirmed.'
                    : 'Your interests aren’t confirmed yet.'}
                </h3>
                <p>
                  {receipt.confirmed
                    ? 'The planning service returned the interest shares you chose. Continue in chat to confirm your locations and review any remaining details.'
                    : 'Your draft is kept. The service did not confirm all the interest shares, or some details need attention. Retry or continue in chat to resolve them.'}
                </p>
                {Object.entries(receipt.validationIssues ?? {}).map(([key, value]) => (
                  <p key={key}>{String(value)}</p>
                ))}
                <button type="button" className="setup-primary" onClick={onContinue}>
                  Continue in chat
                </button>
              </div>
            )}
          </div>
          <footer className="setup-footer">
            <button
              type="button"
              className="setup-secondary"
              onClick={() => go(step - 1)}
              disabled={step === 0 || locked}
            >
              Back
            </button>
            <span>{stored ? 'Draft saved in this browser tab' : 'Draft kept on this screen'}</span>
            <button type="submit" className="setup-primary" disabled={locked}>
              {locked
                ? 'Checking with the planning service…'
                : step === 4
                  ? 'Send details for confirmation'
                  : 'Next'}
            </button>
          </footer>
        </form>
        <div className="setup-bottom-actions">
          <button
            type="button"
            className="setup-text-button"
            disabled={locked}
            onClick={onContinue}
          >
            Prefer to chat?
          </button>
          <button
            type="button"
            className="setup-text-button"
            disabled={locked}
            onClick={() => setResetOpen((open) => !open)}
          >
            Reset draft
          </button>
        </div>
        {resetOpen && (
          <div className="setup-reset" role="group" aria-label="Reset draft confirmation">
            <p>Clear these draft answers? Saved trips will stay available.</p>
            <button type="button" className="setup-secondary" onClick={() => setResetOpen(false)}>
              Keep answers
            </button>
            <button
              type="button"
              className="setup-secondary"
              onClick={() => {
                reset();
                setVisited(0);
                setErrors({});
                setReceipt(null);
                setResetOpen(false);
              }}
            >
              Clear draft answers
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
TripSetup.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  onContinue: PropTypes.func.isRequired,
  busy: PropTypes.bool,
};
