import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import useSetupDraft from './useSetupDraft';
import { ActionButton, AmountControl, ChoiceGroup, DesignFrame, Field, Sheet } from '../../design';
import {
  INTERESTS,
  COMPARISONS,
  STEPS,
  newSetupDraft,
  preferenceProfiles,
  setupErrors,
} from './setupModel';
import './TripSetup.css';
import DailyRhythm from './DailyRhythm.jsx';
import PreferenceProfilePicker from '../../components/PreferenceProfilePicker';

const INTEREST_LABELS = {
  scenery: 'Scenery',
  nature: 'Nature',
  hiking_outdoors: 'Hikes',
  food: 'Food',
  history: 'History',
  culture_arts: 'Arts',
  nightlife: 'Nightlife',
  shopping: 'Shopping',
  beaches_water: 'Water',
  adventure: 'Adventure',
  relaxation: 'Relaxation',
  unique_local_experiences: 'Local places',
  family_friendliness: 'Family',
  crowd_avoidance: 'Quiet',
};

export default function TripSetup({ onSubmit, busy = false, renderEstimate, prepareRoute }) {
  const { draft, setDraft, step, setStep, stored, reset } = useSetupDraft();
  const [errors, setErrors] = useState({});
  const [receipt, setReceipt] = useState(null);
  const [sending, setSending] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [largeText, setLargeText] = useState(false);
  const textProbe = useRef(null);
  const [comparisonIndex, setComparisonIndex] = useState(0);
  const [interestView, setInterestView] = useState('choices');
  const [editedInterest, setEditedInterest] = useState('food');
  const setupPercent = [0, 25, 35, 38, 40][step];
  const [amountReset, setAmountReset] = useState(0);
  const heading = useRef(null);
  const comparisonTrigger = useRef(null);
  const amountTrigger = useRef(null);
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
    setInterestView('choices');
  };
  const next = async () => {
    const issues = setupErrors(draft, step);
    if (Object.keys(issues).length) setErrors(issues);
    else {
      if (step === 0 && prepareRoute) {
        setSending(true);
        try {
          const prepared = await prepareRoute();
          if (!alive.current) return;
          if (!prepared?.ok) {
            setErrors({
              start: 'Confirm the locations and a usable road route before continuing.',
            });
            return;
          }
        } finally {
          if (alive.current) setSending(false);
        }
      }
      go(step + 1);
    }
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
      if (prepareRoute) {
        const prepared = await prepareRoute();
        if (!alive.current) return;
        if (!prepared?.ok) {
          setStep(0);
          setErrors({ start: 'Confirm the locations and a usable road route before continuing.' });
          return;
        }
      }
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
        <Sheet className={`setup-card setup-card--${interestView}`} aria-label="Plan your trip">
          <nav aria-label="Trip setup progress" className="setup-progress">
            <p>
              <span>Trip details · {setupPercent}%</span>
            </p>
            <progress aria-label="Trip setup completion" value={setupPercent} max={100} />
          </nav>
          {renderEstimate?.(draft, step)}
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
                    <div className="setup-grid">
                      {field('date', 'Departure date', 'date')}
                      {field('time', 'Departure time', 'time')}
                    </div>
                    <p className="setup-hint">Departure uses your starting location’s time.</p>
                  </>
                )}
                {step === 1 && (
                  <>
                    {field('travelers', 'Total people, including you', 'number', {
                      min: 1,
                      step: 1,
                      inputMode: 'numeric',
                    })}
                    {field('stops', 'How many attractions would you like?', 'number', {
                      min: 1,
                      step: 1,
                      inputMode: 'numeric',
                    })}
                  </>
                )}
                {step === 2 && (
                  <>
                    <div className="setup-interest-choices" hidden={interestView !== 'choices'}>
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
                              aria-label={
                                INTEREST_LABELS[key] && INTEREST_LABELS[key] !== label
                                  ? `${INTEREST_LABELS[key]} · ${label}`
                                  : label
                              }
                              checked={draft.interests.includes(key)}
                              onChange={() => toggleInterest(key)}
                            />
                            <span>{INTEREST_LABELS[key] ?? label}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="setup-interest-tools">
                      <details
                        className="setup-explanation setup-comparison-panel"
                        open={interestView === 'comparisons'}
                        onToggle={(event) => {
                          if (event.currentTarget.open) setInterestView('comparisons');
                          else
                            setInterestView((current) =>
                              current === 'comparisons' ? 'choices' : current
                            );
                        }}
                      >
                        <summary ref={comparisonTrigger}>Compare places</summary>
                        <section className="setup-comparisons" aria-labelledby="comparison-heading">
                          <div className="setup-group-heading">
                            <h3 id="comparison-heading">Which stop feels more like you?</h3>
                          </div>
                          <p className="setup-hint" aria-live="polite">
                            Examples only · {comparisonIndex + 1} of {COMPARISONS.length}
                          </p>
                          <div className="setup-comparison-places">
                            {[comparison.left, comparison.right].map((place, index) => (
                              <article className="setup-place" key={place.id}>
                                <input
                                  type="radio"
                                  id={`compare-${comparison.id}-${index}`}
                                  name={comparison.id}
                                  aria-labelledby={`compare-title-${comparison.id}-${index}`}
                                  checked={
                                    draft.comparisonAnswers?.[comparison.id] ===
                                    (index === 0 ? 'left' : 'right')
                                  }
                                  onChange={() => answerComparison(index === 0 ? 'left' : 'right')}
                                />
                                <h4 id={`compare-title-${comparison.id}-${index}`}>{place.name}</h4>
                                <p>{place.character ?? place.description}</p>
                              </article>
                            ))}
                          </div>
                          <ChoiceGroup
                            legend="Which would you choose?"
                            name={comparison.id}
                            value={draft.comparisonAnswers?.[comparison.id]}
                            onChange={answerComparison}
                            options={[
                              { value: 'either', label: 'Either place' },
                              { value: 'neither', label: 'Neither place' },
                              { value: 'unsure', label: 'Not sure' },
                            ]}
                          />
                          <div className="setup-inline-actions">
                            <ActionButton
                              variant="secondary"
                              disabled={comparisonIndex === 0}
                              aria-label="Previous comparison"
                              onClick={() => setComparisonIndex((index) => index - 1)}
                            >
                              Previous
                            </ActionButton>
                            <ActionButton
                              variant="secondary"
                              disabled={comparisonIndex === COMPARISONS.length - 1}
                              aria-label="Next comparison"
                              onClick={() => setComparisonIndex((index) => index + 1)}
                            >
                              Next
                            </ActionButton>
                          </div>
                          <div className="setup-inline-actions">
                            <button
                              type="button"
                              className="setup-text-button"
                              aria-label="Skip this comparison"
                              onClick={() => {
                                answerComparison('unsure');
                                setComparisonIndex((index) =>
                                  Math.min(index + 1, COMPARISONS.length - 1)
                                );
                              }}
                            >
                              Skip
                            </button>
                            <button
                              type="button"
                              className="setup-text-button"
                              aria-label="Reset comparisons"
                              onClick={() => {
                                set('comparisonAnswers', {});
                                setComparisonIndex(0);
                              }}
                            >
                              Reset
                            </button>
                          </div>
                        </section>
                      </details>
                      <details
                        className="setup-explanation setup-amount-panel"
                        open={interestView === 'amounts'}
                        onToggle={(event) => {
                          if (event.currentTarget.open) setInterestView('amounts');
                          else
                            setInterestView((current) =>
                              current === 'amounts' ? 'choices' : current
                            );
                        }}
                      >
                        <summary ref={amountTrigger}>Adjust amounts</summary>
                        <label className="setup-field" htmlFor="setup-amount-choice">
                          Interest to adjust
                          <select
                            id="setup-amount-choice"
                            value={editedInterest}
                            onChange={(event) => setEditedInterest(event.target.value)}
                          >
                            {Object.entries(INTERESTS).map(([key, label]) => (
                              <option key={key} value={key}>
                                {label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <p id="setup-interest-amount-hint" className="setup-hint">
                          Drag or tap − / +. Keep at least one amount above zero. Picking interests
                          again resets these amounts.
                        </p>
                        <AmountControl
                          key={`${editedInterest}:${amountReset}`}
                          id={`setup-interest-${editedInterest}`}
                          label={INTERESTS[editedInterest]}
                          value={interestAmounts[editedInterest]}
                          initialMax={initialAmountMax}
                          disabled={locked}
                          describedBy="setup-interest-amount-hint"
                          onChange={(value) =>
                            set('customWeights', { ...interestAmounts, [editedInterest]: value })
                          }
                        />
                      </details>
                    </div>
                    {interestView !== 'choices' && (
                      <ActionButton
                        variant="secondary"
                        onClick={() => {
                          const trigger =
                            interestView === 'comparisons' ? comparisonTrigger : amountTrigger;
                          setInterestView('choices');
                          trigger.current?.focus({ preventScroll: true });
                        }}
                      >
                        Done adjusting interests
                      </ActionButton>
                    )}
                    {errors.interests && <p className="setup-error">{errors.interests}</p>}
                    <div className="setup-interest-actions" hidden={interestView !== 'choices'}>
                      <button
                        type="button"
                        className="setup-text-button setup-interest-reset"
                        hidden={interestView !== 'choices'}
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
                        className="setup-text-button setup-interest-skip"
                        aria-label="Skip interests and use a balanced mix"
                        hidden={interestView !== 'choices'}
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
                        Use a balanced mix
                      </button>
                    </div>
                  </>
                )}
                {step === 3 && (
                  <>
                    <DailyRhythm
                      value={draft.dailyRhythm}
                      onChange={(value) => set('dailyRhythm', value)}
                      disabled={locked}
                      error={errors.schedule}
                    />
                  </>
                )}
                {step === 4 && (
                  <>
                    <div className="setup-review">
                      {[
                        [
                          'Where and when',
                          draft.start + ' → ' + draft.destination,
                          draft.date + ' at ' + draft.time,
                        ],
                        [
                          'People',
                          draft.travelers + (Number(draft.travelers) === 1 ? ' person' : ' people'),
                          draft.stops + ' attractions',
                        ],
                        [
                          'What you enjoy',
                          draft.customWeights
                            ? 'Custom amounts'
                            : draft.interests.length
                              ? draft.interests.length > 3
                                ? `${draft.interests.length} interests`
                                : draft.interests.map((key) => INTERESTS[key]).join(', ')
                              : 'A balanced mix',
                          '',
                        ],
                        [
                          'Daily timing',
                          draft.dailyRhythm
                            ? 'Your driving, rest and sleep rhythm'
                            : 'Your existing daily timing',
                          '',
                        ],
                      ].map(([title, primary, secondary], index) => (
                        <section key={title}>
                          <div>
                            <h3>{title}</h3>
                            <p>{primary}</p>
                            {secondary && <p className="setup-hint">{secondary}</p>}
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
                      Check trip options, then choose one day or overnight stays.
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
              <ActionButton type="submit" disabled={locked}>
                {locked ? 'Checking locations…' : step === 4 ? 'Check trip options' : 'Next'}
              </ActionButton>
            </footer>
          </form>
          <div className="setup-bottom-actions">
            <span className="rt-caption">{stored ? 'Draft saved' : 'Draft kept'}</span>
            <Link to="/trips">Saved trips</Link>
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
  prepareRoute: PropTypes.func,
};
