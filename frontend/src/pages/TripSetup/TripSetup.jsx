import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import useSetupDraft from './useSetupDraft';
import { ActionButton, AmountControl, ChoiceGroup, DesignFrame, Field, Sheet } from '../../design';
import {
  INTERESTS,
  COMPARISONS,
  MAX_SETUP_ROOMS,
  STEPS,
  newSetupDraft,
  preferenceProfiles,
  setupErrors,
} from './setupModel';
import './TripSetup.css';
import PreferenceProfilePicker from '../../components/PreferenceProfilePicker';

export default function TripSetup({ onSubmit, busy = false, renderEstimate }) {
  const { draft, setDraft, step, setStep, stored, reset } = useSetupDraft();
  const [errors, setErrors] = useState({});
  const [receipt, setReceipt] = useState(null);
  const [sending, setSending] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [largeText, setLargeText] = useState(false);
  const textProbe = useRef(null);
  const [comparisonIndex, setComparisonIndex] = useState(0);
  const [amountReset, setAmountReset] = useState(0);
  const heading = useRef(null);
  const errorSummary = useRef(null);
  const alive = useRef(true);
  const previousStep = useRef(step);
  const locked = busy || sending;
  let profiles;
  try {
    profiles = preferenceProfiles(draft);
  } catch {
    profiles = preferenceProfiles(newSetupDraft());
  }
  const interestAmounts =
    draft.customWeights ??
    Object.fromEntries(Object.entries(profiles.stated).map(([key, value]) => [key, value * 100]));
  const largestAmount = Math.max(...Object.values(interestAmounts));
  const initialAmountMax =
    largestAmount > Number.MAX_VALUE / 2 ? Number.MAX_VALUE : largestAmount * 2 || 1;

  const comparison = COMPARISONS[comparisonIndex];

  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() =>
      setLargeText(textProbe.current.getBoundingClientRect().width > 24)
    );
    observer.observe(textProbe.current);
    return () => observer.disconnect();
  }, []);
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
      const result = await onSubmit({ draft });
      if (!alive.current) return;
      setReceipt(result?.error ? result : null);
    } catch {
      if (alive.current)
        setReceipt({
          error: 'Could not check the locations. Your draft is kept. Please try again.',
        });
    } finally {
      if (alive.current) setSending(false);
    }
  };
  const field = (key, label, type = 'text', extra = {}) => (
    <Field
      id={'setup-' + key}
      label={label}
      type={type}
      value={draft[key]}
      onChange={(event) => set(key, event.target.value)}
      error={errors[key]}
      {...extra}
    />
  );
  const updateRoom = (index, key, value) =>
    set(
      'rooms',
      draft.rooms.map((room, i) => (i === index ? { ...room, [key]: value } : room))
    );
  const toggleInterest = (key) => {
    setAmountReset((previous) => previous + 1);
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
  const answerComparison = (answer) => {
    set('comparisonAnswers', { ...draft.comparisonAnswers, [comparison.id]: answer });
  };

  return (
    <DesignFrame className={'setup-design' + (largeText ? ' setup-design--large-text' : '')}>
      <span ref={textProbe} className="setup-text-probe" aria-hidden="true" />
      <main className="trip-setup">
        <div className="setup-wayfinding">
          <Link to="/">Home</Link>
          <Link to="/trips">Saved trips</Link>
        </div>
        <Sheet className="setup-card" aria-label="Plan your trip">
          <nav aria-label="Trip setup progress" className="setup-progress">
            <p>
              <span>{Math.round((step / (STEPS.length - 1)) * 100)}%</span>
            </p>
            <progress aria-label="Trip setup completion" value={step} max={STEPS.length - 1} />
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
                {step === 4 && (
                  <p className="rt-caption">
                    Your car, timing and chosen interests will be saved as reusable preferences when
                    this trip is saved.
                  </p>
                )}
                {step === 0 && (
                  <>
                    <PreferenceProfilePicker
                      setDraft={(updater) => {
                        setDraft(updater);
                        setErrors({});
                        setReceipt(null);
                      }}
                      disabled={locked}
                    />
                    {field('start', 'Starting city or address', 'text', {
                      autoComplete: 'off',
                      maxLength: 256,
                    })}
                    {field('destination', 'Destination', 'text', {
                      autoComplete: 'off',
                      maxLength: 256,
                    })}
                    {renderEstimate?.(draft)}
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
                        onClick={() =>
                          set('rooms', [...draft.rooms, { adults: '1', children: '' }])
                        }
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
                    <p>Choose your interests, or keep a balanced mix.</p>
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
                    <details className="setup-explanation">
                      <summary>Refine with place comparisons</summary>
                      <section className="setup-comparisons" aria-labelledby="comparison-heading">
                        <div className="setup-group-heading">
                          <p className="setup-eyebrow">
                            Optional · {COMPARISONS.length} quick comparisons
                          </p>
                          <h3 id="comparison-heading">Which stop feels more like you?</h3>
                          <p className="setup-hint">
                            Compare real places to add a second perspective. These examples aren’t
                            route recommendations.
                          </p>
                        </div>
                        <p className="setup-hint" aria-live="polite">
                          Comparison {comparisonIndex + 1} of {COMPARISONS.length}
                        </p>
                        <div className="setup-comparison-places">
                          {[comparison.left, comparison.right].map((place, index) => (
                            <article className="setup-place" key={place.id}>
                              <span className="setup-place-marker" aria-hidden="true">
                                {index === 0 ? 'A' : 'B'}
                              </span>
                              <h4>{place.name}</h4>
                              <p>{place.character ?? place.description}</p>
                              <details className="setup-source">
                                <summary>Place source</summary>
                                <p>{place.source_attribution}</p>
                                <a href={place.url} target="_blank" rel="noreferrer">
                                  Visitor information
                                  <span className="setup-visually-hidden">
                                    {' '}
                                    for {place.name} (new tab)
                                  </span>
                                </a>
                              </details>
                            </article>
                          ))}
                        </div>
                        <ChoiceGroup
                          legend="Which would you choose?"
                          name={comparison.id}
                          value={draft.comparisonAnswers?.[comparison.id]}
                          onChange={answerComparison}
                          options={[
                            { value: 'left', label: comparison.left.name },
                            { value: 'right', label: comparison.right.name },
                            { value: 'either', label: 'Either place' },
                            { value: 'neither', label: 'Neither place' },
                            { value: 'unsure', label: 'Not sure' },
                          ]}
                        />
                        <div className="setup-inline-actions">
                          <ActionButton
                            variant="secondary"
                            disabled={comparisonIndex === 0}
                            onClick={() => setComparisonIndex((index) => index - 1)}
                          >
                            Previous comparison
                          </ActionButton>
                          <ActionButton
                            variant="secondary"
                            disabled={comparisonIndex === COMPARISONS.length - 1}
                            onClick={() => setComparisonIndex((index) => index + 1)}
                          >
                            Next comparison
                          </ActionButton>
                        </div>
                        <div className="setup-inline-actions">
                          <button
                            type="button"
                            className="setup-text-button"
                            onClick={() => {
                              answerComparison('unsure');
                              setComparisonIndex((index) =>
                                Math.min(index + 1, COMPARISONS.length - 1)
                              );
                            }}
                          >
                            Skip this comparison
                          </button>
                          <button
                            type="button"
                            className="setup-text-button"
                            onClick={() => {
                              set('comparisonAnswers', {});
                              setComparisonIndex(0);
                            }}
                          >
                            Reset comparisons
                          </button>
                        </div>
                      </section>
                    </details>
                    <details className="setup-explanation">
                      <summary>Edit interest amounts</summary>
                      <p id="setup-interest-amount-hint">
                        Drag or tap − / +. Higher amounts give an interest more influence. At least
                        one must stay above zero.
                      </p>
                      <p className="setup-hint">
                        Selecting interests above resets these amounts; comparison choices keep
                        them.
                      </p>
                      <div className="rt-amount-grid">
                        {Object.entries(INTERESTS).map(([key, label]) => (
                          <AmountControl
                            key={`${key}:${amountReset}`}
                            id={`setup-interest-${key}`}
                            label={label}
                            value={interestAmounts[key]}
                            initialMax={initialAmountMax}
                            disabled={locked}
                            describedBy="setup-interest-amount-hint"
                            onChange={(value) =>
                              set('customWeights', { ...interestAmounts, [key]: value })
                            }
                          />
                        ))}
                      </div>
                    </details>
                    {errors.interests && <p className="setup-error">{errors.interests}</p>}
                    <button
                      type="button"
                      className="setup-text-button"
                      onClick={() => {
                        setAmountReset((previous) => previous + 1);
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
                          comparisonAnswers: {},
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
                    <p className="setup-hint">Car details can be added later.</p>
                    <div
                      className="setup-grid"
                      id="setup-schedule"
                      tabIndex={-1}
                      aria-describedby={errors.schedule ? 'setup-schedule-error' : undefined}
                    >
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
                    {errors.schedule && (
                      <p id="setup-schedule-error" className="setup-error">
                        {errors.schedule}
                      </p>
                    )}
                    <p className="setup-hint">
                      Daily times are local to each stop. The planning service checks the final
                      schedule.
                    </p>
                  </>
                )}
                {step === 4 && (
                  <>
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
                          draft.customWeights
                            ? 'Your custom interest amounts'
                            : draft.interests.length
                              ? draft.interests.map((key) => INTERESTS[key]).join(', ')
                              : 'A balanced mix across all interests',
                          '',
                        ],
                        [
                          'Daily timing',
                          draft.schedule.late_driving ? 'Later evenings' : 'Standard evenings',
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
                    <p className="setup-hint">
                      Next, confirm the suggested addresses. Your choices help tailor the stops for
                      this trip. Prices and travel-time estimates arrive with the route.
                    </p>
                  </>
                )}
              </fieldset>
              {receipt?.error && (
                <div className="setup-error-summary" role="alert">
                  <h3>We couldn’t check those locations yet.</h3>
                  <p>{receipt.error}</p>
                  <p>Your draft is kept. Refine the addresses or try again.</p>
                </div>
              )}
            </div>
            <footer className="setup-footer">
              <ActionButton
                variant="secondary"
                onClick={() => go(step - 1)}
                disabled={step === 0 || locked}
              >
                Back
              </ActionButton>
              <span>{stored ? 'Draft saved' : 'Draft kept'}</span>
              <ActionButton type="submit" disabled={locked}>
                {locked ? 'Checking locations…' : step === 4 ? 'Check locations' : 'Next'}
              </ActionButton>
            </footer>
          </form>
          <div className="setup-bottom-actions">
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
                  setErrors({});
                  setReceipt(null);
                  setResetOpen(false);
                }}
              >
                Clear draft answers
              </button>
            </div>
          )}
        </Sheet>
      </main>
    </DesignFrame>
  );
}
TripSetup.propTypes = {
  onSubmit: PropTypes.func.isRequired,
  busy: PropTypes.bool,
  renderEstimate: PropTypes.func,
};
