import { useContext, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChatData, Data, UserDataContext } from '../../states/UserDataContext';
import { initializeUserData, ensureChatCreated, updateUserData } from '../../services/savedTrips';
import { getSession, isCurrentSession } from '../../services/session';
import {
  planStructuredItinerary,
  plannerError,
  structuredTripInputs,
} from '../../services/tripPlanner';
import TripSetup from './TripSetup';
import { ActionButton, DesignFrame, Sheet } from '../../design';
import { hotelSetupErrors, preferenceProfiles } from './setupModel';
import { advancePlanningProgress, newPlanningProgress } from '../../services/tripPlanningProgress';
import {
  assessPlanningCandidate,
  buildCandidatePayload,
  cancelCandidateRequest,
  confirmPlanningCandidate,
  registerCandidateRequest,
} from '../../services/planningCandidates';
import { candidateErrorMessage } from '../../services/planningCandidateErrors';
import HotelQuestions from './HotelQuestions';
import OnboardingMap from './OnboardingMap';
import RouteEstimate from './RouteEstimate';
import PlanningProgress from './PlanningProgress';
import './ConnectedPlanning.css';
import { saveNewTripPreferences } from '../../services/preferenceProfiles';

export default function TripSetupPage() {
  const { setUserData, setChats } = useContext(UserDataContext);
  const [loaded, setLoaded] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [proposal, setProposal] = useState(null);
  const [selections, setSelections] = useState({ origin: 0, destination: 0 });
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [preferenceNotice, setPreferenceNotice] = useState('');
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(newPlanningProgress);
  const report = (event) => setProgress((old) => advancePlanningProgress(old, event));
  const request = useRef(null);
  const preparation = useRef(null);
  const estimate = useRef(null);
  const attempt = useRef(null);
  const [candidate, setCandidate] = useState(null);
  const [preview, setPreview] = useState(null);
  const [overnight, setOvernight] = useState(false);
  const [hotelErrors, setHotelErrors] = useState({});
  const clearCandidate = () => {
    const old = attempt.current;
    attempt.current = null;
    if (old) cancelCandidateRequest(old.requestId, old.session).catch(() => {});
    setCandidate(null);
    setPreview(null);
    setOvernight(false);
    setHotelErrors({});
  };
  const heading = useRef(null);
  const textProbe = useRef(null);
  const [largeText, setLargeText] = useState(false);
  useEffect(() => {
    if (!textProbe.current || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() =>
      setLargeText(textProbe.current?.getBoundingClientRect().width > 24)
    );
    observer.observe(textProbe.current);
    return () => observer.disconnect();
  }, [proposal, loaded]);
  const isActive = (controller, session) =>
    request.current === controller && !controller.signal.aborted && isCurrentSession(session);

  useEffect(() => {
    let cancelled = false;
    const session = getSession();
    setLoadError(false);
    const changed = () => {
      if (isCurrentSession(session)) return;
      request.current?.abort();
      request.current = null;
      attempt.current = null;
      setLoaded(null);
      setProposal(null);
      setCandidate(null);
      setResult(null);
      setBusy(false);
      setSaving(false);
      setError('');
      setPreferenceNotice('');
      setProgress(newPlanningProgress());
      setLoadAttempt((old) => old + 1);
    };
    window.addEventListener('auth-changed', changed);
    if (session.owner)
      initializeUserData(session.accessToken).then((data) => {
        if (cancelled || !isCurrentSession(session)) return;
        if (!data) setLoadError(true);
        else setLoaded(data);
      });
    return () => {
      cancelled = true;
      window.removeEventListener('auth-changed', changed);
      request.current?.abort();
      request.current = null;
      const old = attempt.current;
      if (old) cancelCandidateRequest(old.requestId, old.session).catch(() => {});
      attempt.current = null;
    };
  }, [loadAttempt]);

  const proposalReady = Boolean(proposal);
  const resultId = result?.snapshot.chatId;
  const candidateId = candidate?.candidate_id;
  useEffect(() => {
    heading.current?.focus();
  }, [proposalReady, resultId, candidateId, error]);

  const locate = async ({ draft }) => {
    const session = getSession();
    const controller = new AbortController();
    request.current = controller;
    try {
      const ready = preparation.current;
      if (
        !ready ||
        !isCurrentSession(ready.session) ||
        ready.queryKey !== JSON.stringify([draft.start.trim(), draft.destination.trim()])
      )
        return { error: 'Check your road route before continuing.' };
      if (!isActive(controller, session))
        return { error: 'Session changed. Please sign in again.' };
      clearCandidate();
      setSelections({ origin: 0, destination: 0 });
      const nextProposal = {
        draft,
        origin: [ready.origin],
        destination: [ready.destination],
        initialRoute: ready.initialRoute,
      };
      setProposal(nextProposal);
      setError('');
      await checkOptions(nextProposal);
      return { ok: true };
    } catch (failure) {
      return {
        error: failure.message && !failure.response ? failure.message : plannerError(failure),
      };
    } finally {
      if (request.current === controller) request.current = null;
    }
  };

  const save = async (current, session, controller) => {
    if (!isActive(controller, session) || !current.itinerary || !current.snapshot.isComplete)
      return false;
    const logs = loaded.UserData.chatlogs;
    const records = [
      ...loaded.chats.filter((item) => item.id !== current.snapshot.chatId),
      current.record,
    ];
    const saved = current.persisted
      ? await updateUserData(session.accessToken, current.snapshot, records, logs)
      : await ensureChatCreated(session.accessToken, current.snapshot, records, logs);
    if (!isActive(controller, session)) return false;
    if (!saved) {
      current.saveConflict = Boolean(current.snapshot.saveConflict);
      return false;
    }
    if (!current.preferencesSaved) {
      try {
        await saveNewTripPreferences(current.draft, current.preferenceId);
        current.preferencesSaved = true;
        if (isActive(controller, session))
          setPreferenceNotice('Preferences saved for future trips.');
      } catch {
        if (isActive(controller, session))
          setPreferenceNotice('Trip saved. Preferences could not be saved; retry below.');
      }
    }
    if (!isActive(controller, session)) return false;
    const index = logs.chatdata.findIndex((item) => item.chatId === current.snapshot.chatId);
    if (index < 0) logs.addChatData(current.snapshot);
    else logs.chatdata[index] = current.snapshot;
    logs.currentId = current.snapshot.chatId;
    sessionStorage.setItem('selectedChatId', String(logs.currentId));
    setUserData(new Data(logs));
    setChats(records);
    setLoaded({ UserData: new Data(logs), chats: records });
    return true;
  };

  const checkOptions = async (currentProposal = proposal) => {
    if (busy || !currentProposal) return;
    const session = getSession(),
      controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    setProgress(
      advancePlanningProgress(newPlanningProgress(), {
        type: 'progress',
        stage: 'route.initial',
        state: 'completed',
      })
    );
    try {
      if (!attempt.current)
        attempt.current = {
          requestId: crypto.randomUUID(),
          session,
          registered: false,
          payload: null,
        };
      const current = attempt.current;
      if (!isCurrentSession(current.session)) return;
      if (!current.registered) {
        await registerCandidateRequest(current.requestId, controller.signal);
        if (!isActive(controller, session)) return;
        current.registered = true;
      }
      if (!current.payload)
        current.payload = await buildCandidatePayload(
          currentProposal.draft,
          currentProposal.initialRoute,
          current.requestId
        );
      if (!isActive(controller, session)) return;
      const checked = await assessPlanningCandidate(
        currentProposal.draft,
        currentProposal.initialRoute,
        current.requestId,
        controller.signal,
        (event) => {
          if (!isActive(controller, session)) return;
          if (
            event.stage === 'route.preview' &&
            event.preview_only === true &&
            event.phase === 'checking' &&
            event.geometry?.type === 'LineString'
          )
            setPreview({ geometry: event.geometry, stops: event.stops ?? [] });
          report(event);
        },
        current.payload
      );
      if (!isActive(controller, session)) return;
      setCandidate(checked);
      setPreview(null);
      report({ type: 'progress', stage: 'candidate.checked', state: 'completed' });
    } catch (failure) {
      if (!isActive(controller, session)) return;
      setError(plannerError(failure));
      report({ type: 'failed' });
      if (
        candidateErrorMessage(failure.response?.status, failure.response?.data?.code) &&
        [
          'candidate_expired',
          'candidate_cancelled',
          'candidate_inputs_changed',
          'candidate_already_confirmed',
          'candidate_unavailable',
        ].includes(failure.response.data.code)
      )
        clearCandidate();
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
      }
    }
  };

  const plan = async (mode) => {
    if (busy || !proposal || !candidate) return;
    if (mode === 'overnight') {
      const issues = hotelSetupErrors(proposal.draft);
      setHotelErrors(issues);
      if (Object.keys(issues).length) return;
    }
    if (selections.origin < 0 || selections.destination < 0) {
      setError('Choose both confirmed locations before planning.');
      return;
    }
    const session = getSession(),
      controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    setPreferenceNotice('');
    report({ type: 'resume' });
    try {
      const origin = proposal.origin[selections.origin],
        destination = proposal.destination[selections.destination];
      const route = await confirmPlanningCandidate(
        candidate,
        mode,
        proposal.draft,
        controller.signal
      );
      if (!isActive(controller, session)) return;
      report({ type: 'progress', stage: 'route.ready', state: 'completed' });
      // IDs are allocated only after owner-scoped saved records have loaded.
      const id = Math.max(0, ...loaded.UserData.chatlogs.chatdata.map((item) => item.chatId)) + 1;
      const snapshot = new ChatData(id);
      Object.assign(snapshot, {
        agentChatId: crypto.randomUUID(),
        route,
        itinerary: null,
        startConfirmed: origin,
        endConfirmed: destination,
        startCoords: [origin.latitude, origin.longitude],
        endCoords: [destination.latitude, destination.longitude],
        stops: Number(proposal.draft.stops),
        // Preserve fractional targets in tripProfile; the legacy hotelBudget slot is integer-only.
        carDetails: [proposal.draft.year, proposal.draft.make, proposal.draft.model],
        isComplete: false,
        tripProfile: {
          ...structuredTripInputs(proposal.draft),
          reserve_meal_slots: true,
          trip_mode: mode,
          ...(mode === 'one_day' ? { hotel_rooms: [], budget: null } : {}),
          preference_profiles: preferenceProfiles(proposal.draft),
          start_address: origin.address,
          destination_address: destination.address,
          start_timezone: route.start_timezone,
          car_status: proposal.draft.carStatus,
          departure_time: proposal.draft.time,
          start_date: route.departure_time,
          start_coords: [origin.latitude, origin.longitude],
          destination_coords: [destination.latitude, destination.longitude],
          ...(proposal.draft.carStatus === 'provided'
            ? {
                car: {
                  year: Number(proposal.draft.year),
                  make: proposal.draft.make,
                  model: proposal.draft.model,
                },
              }
            : {}),
        },
      });
      const current = {
        draft: proposal.draft,
        preferenceId: crypto.randomUUID(),
        route,
        snapshot,
        record: { id, title: origin.address + ' → ' + destination.address, messages: [] },
        weights: structuredTripInputs(proposal.draft).persona_weights,
        saved: false,
        persisted: false,
      };
      try {
        const itinerary = await planStructuredItinerary(route, controller.signal, {
          includeMealSlots: true,
        });
        if (!isActive(controller, session)) return;
        current.itinerary = itinerary;
        snapshot.itinerary = itinerary;
        snapshot.isComplete = true;
        report({ type: 'progress', stage: 'itinerary.ready', state: 'completed' });
      } catch (failure) {
        if (!isActive(controller, session)) return;
        current.itineraryError = plannerError(failure);
        report({ type: 'failed' });
      }
      if (!current.itinerary) {
        setResult(current);
        return;
      }
      setSaving(true);
      current.saved = await save(current, session, controller);
      if (!isActive(controller, session)) return;
      current.persisted = current.persisted || current.saved;
      report(
        current.saved
          ? { type: 'progress', stage: 'trip.saved', state: 'completed' }
          : { type: 'failed' }
      );
      setSaving(false);
      if (!isActive(controller, session)) return;
      setResult(current);
      if (!current.saved)
        setError(
          current.saveConflict
            ? 'A newer version of this trip is already saved. Open Saved trips to reload it before editing.'
            : 'The route is available, but it could not be saved. Retry saving before leaving.'
        );
    } catch (failure) {
      if (isActive(controller, session)) {
        setError(plannerError(failure));
        if (
          candidateErrorMessage(failure.response?.status, failure.response?.data?.code) &&
          [
            'candidate_expired',
            'candidate_cancelled',
            'candidate_inputs_changed',
            'candidate_already_confirmed',
            'candidate_unavailable',
          ].includes(failure.response.data.code)
        )
          clearCandidate();
        report({ type: 'failed' });
      }
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
        setSaving(false);
      }
    }
  };

  const retry = async (itineraryOnly) => {
    if (busy || !result || (!itineraryOnly && !result.itinerary)) return;
    const session = getSession(),
      controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    report({ type: 'resume' });
    try {
      const next = { ...result, snapshot: { ...result.snapshot } };
      if (itineraryOnly) {
        const itinerary = await planStructuredItinerary(result.route, controller.signal, {
          includeMealSlots: true,
        });
        if (!isActive(controller, session)) return;
        next.itinerary = itinerary;
        next.snapshot.itinerary = itinerary;
        next.snapshot.isComplete = true;
        next.itineraryError = '';
        report({ type: 'progress', stage: 'itinerary.ready', state: 'completed' });
      }
      if (!isActive(controller, session)) return;
      setSaving(true);
      next.saved = await save(next, session, controller);
      if (!isActive(controller, session)) return;
      next.persisted = next.persisted || next.saved;
      report(
        next.saved
          ? { type: 'progress', stage: 'trip.saved', state: 'completed' }
          : { type: 'failed' }
      );
      setSaving(false);
      if (!isActive(controller, session)) return;
      setResult(next);
      if (!next.saved)
        setError(
          next.saveConflict
            ? 'A newer version of this trip is already saved. Open Saved trips to reload it before editing.'
            : 'This trip could not be saved. Please retry before leaving.'
        );
    } catch (failure) {
      if (isActive(controller, session)) {
        setError(plannerError(failure));
        report({ type: 'failed' });
      }
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
        setSaving(false);
      }
    }
  };

  const retryPreferences = async () => {
    if (busy || !result) return;
    const session = getSession();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    try {
      await saveNewTripPreferences(result.draft, result.preferenceId);
      if (!isActive(controller, session)) return;
      setResult((old) => ({ ...old, preferencesSaved: true }));
      setPreferenceNotice('Preferences saved for future trips.');
    } catch {
      if (isActive(controller, session))
        setPreferenceNotice('Preferences could not be saved. Please retry.');
    } finally {
      if (request.current === controller) {
        request.current = null;
        setBusy(false);
      }
    }
  };

  if (loadError)
    return (
      <DesignFrame className="setup-design">
        <main className="trip-setup">
          <Sheet aria-label="Saved trips unavailable">
            <div role="alert">
              <h1 className="rt-display">Saved trips could not be loaded.</h1>
              <p className="rt-copy">Retry before creating a new trip.</p>
            </div>
            <ActionButton onClick={() => setLoadAttempt((value) => value + 1)}>
              Retry loading trips
            </ActionButton>
          </Sheet>
        </main>
      </DesignFrame>
    );
  if (!loaded)
    return (
      <DesignFrame className="setup-design">
        <main className="trip-setup">
          <p role="status" className="rt-copy">
            Loading your saved trips…
          </p>
        </main>
      </DesignFrame>
    );
  if (!proposal)
    return (
      <TripSetup
        onSubmit={locate}
        prepareRoute={() => estimate.current?.prepare()}
        renderEstimate={(draft, stage) => (
          <RouteEstimate
            ref={estimate}
            start={draft.start}
            destination={draft.destination}
            draft={draft}
            stage={stage}
            onPrepared={(value) => {
              preparation.current = value;
            }}
          />
        )}
      />
    );

  return (
    <DesignFrame className={'setup-design' + (largeText ? ' setup-design--large-text' : '')}>
      <span ref={textProbe} className="setup-text-probe" aria-hidden="true" />
      <main className="trip-setup">
        <nav className="connected-links" aria-label="Trip navigation">
          <Link to="/">Home</Link>
          <Link to="/trips">Saved trips</Link>
        </nav>
        {progress.percent > 0 && <PlanningProgress progress={progress} />}
        <Sheet
          className="setup-card connected-card"
          aria-label={result ? 'Your trip' : 'Review and confirm'}
        >
          {!result && <p className="rt-caption">Review · Step 5 of 5</p>}
          <h1 ref={heading} tabIndex={-1} className="rt-display">
            {result ? 'Your trip' : candidate ? 'Choose your trip' : 'Check trip options'}
          </h1>
          {error && (
            <p role="alert" className="connected-error">
              {error}
            </p>
          )}
          {!result && (
            <>
              <OnboardingMap
                origin={proposal.origin[0]}
                destination={proposal.destination[0]}
                route={candidate?.candidate_route ?? preview ?? proposal.initialRoute}
                phase={candidate?.candidate_route ? 'candidate' : preview ? 'checking' : 'draft'}
                stage={4}
              />
              <p className="rt-caption">
                {proposal.origin[0].address} → {proposal.destination[0].address} ·{' '}
                {proposal.draft.date}, {proposal.draft.time} local to your start.
              </p>
              {!candidate && (
                <p className="rt-copy">
                  Check the complete route, visits and meal breaks before choosing one day or
                  allowing stays.
                </p>
              )}
              {!candidate && (
                <p className="rt-caption">
                  This action uses AI place ratings and live road providers. No hotels are checked
                  yet.
                </p>
              )}
              {candidate && (
                <>
                  {candidate.one_day.eligible ? (
                    <p className="rt-copy">
                      This checked candidate fits in{' '}
                      {(candidate.one_day.elapsed_seconds / 3600).toFixed(1)} hours, including
                      visits and meal breaks.
                    </p>
                  ) : (
                    <p className="rt-copy">
                      A complete trip under 12 hours could not be verified. Allow overnight stays,
                      or edit your answers.
                    </p>
                  )}
                  {candidate.one_day.eligible && (
                    <ActionButton disabled={busy} onClick={() => plan('one_day')}>
                      Finish in one day
                    </ActionButton>
                  )}
                  <ActionButton
                    variant="secondary"
                    disabled={busy}
                    onClick={() => setOvernight(true)}
                  >
                    Allow overnight stays
                  </ActionButton>
                  {overnight && (
                    <>
                      <HotelQuestions
                        draft={proposal.draft}
                        disabled={busy}
                        errors={hotelErrors}
                        onChange={(draft) => {
                          setProposal((old) => ({ ...old, draft }));
                          setHotelErrors({});
                        }}
                      />
                      <p className="rt-caption">
                        Stays are added only when needed. Quotes do not book a room. Night-driving
                        rhythms may require a one-day trip.
                      </p>
                      <ActionButton disabled={busy} onClick={() => plan('overnight')}>
                        Plan with stays allowed
                      </ActionButton>
                    </>
                  )}
                </>
              )}
              <ActionButton
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  clearCandidate();
                  setProposal(null);
                  setError('');
                  setProgress(newPlanningProgress());
                }}
              >
                Edit answers
              </ActionButton>
              {!candidate && (
                <ActionButton disabled={busy} onClick={() => checkOptions()}>
                  {attempt.current ? 'Retry trip option check' : 'Check trip options'}
                </ActionButton>
              )}
            </>
          )}
          {busy && (
            <div className="rt-stack">
              <p className="rt-caption">
                Working on your trip. Provider checks can take several minutes.
              </p>
              <ActionButton
                variant="secondary"
                disabled={saving}
                onClick={() => {
                  request.current?.abort();
                  request.current = null;
                  clearCandidate();
                  setBusy(false);
                  report({ type: 'failed' });
                  setError(
                    'Stopped waiting. Your draft is kept. A request already received by the service may still finish.'
                  );
                }}
              >
                Stop waiting
              </ActionButton>
            </div>
          )}
          {result && (
            <>
              <OnboardingMap
                origin={{ ...result.snapshot.startConfirmed, confirmed: true }}
                destination={{ ...result.snapshot.endConfirmed, confirmed: true }}
                route={result.route}
                phase="confirmed"
                stage={4}
              />
              <p role="status" className="rt-copy">
                {result.saved
                  ? 'Trip saved.'
                  : result.saveConflict
                    ? 'Saved trip changed; reload required.'
                    : 'Trip is not saved yet.'}
              </p>
              <dl className="connected-summary">
                <dt>Driving distance</dt>
                <dd>{(result.route.distance / 1609.344).toFixed(1)} miles</dd>
                <dt>Driving time</dt>
                <dd>{(result.route.duration / 3600).toFixed(1)} hours</dd>
                <dt>Quoted hotel total</dt>
                <dd>
                  {Number.isFinite(result.route.cost)
                    ? '$' + result.route.cost.toFixed(2)
                    : 'Unavailable'}
                </dd>
              </dl>
              <p className="rt-caption">
                Driving excludes visits, meal breaks and overnight stays. Hotel quotes exclude fuel,
                food and tickets and do not guarantee booking availability.
              </p>
              {(result.route.warnings ?? []).map((warning, index) => (
                <p role="note" key={index} className="rt-caption">
                  {warning}
                </p>
              ))}
              <ActionButton
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  clearCandidate();
                  setResult(null);
                  setProposal(null);
                  setError('');
                  setProgress(newPlanningProgress());
                }}
              >
                Edit draft for another trip
              </ActionButton>
              {preferenceNotice && (
                <p role="status" className="rt-caption">
                  {preferenceNotice}
                </p>
              )}
              {result.saved && !result.preferencesSaved && (
                <ActionButton variant="secondary" disabled={busy} onClick={retryPreferences}>
                  Retry saving preferences
                </ActionButton>
              )}
              {result.itineraryError && (
                <div role="alert" className="rt-stack">
                  <p className="rt-copy">
                    The route is available, but the itinerary could not finish.{' '}
                    {result.itineraryError}
                  </p>
                  <ActionButton variant="secondary" disabled={busy} onClick={() => retry(true)}>
                    Retry itinerary
                  </ActionButton>
                </div>
              )}
              {!result.saved && !result.saveConflict && result.itinerary && (
                <ActionButton disabled={busy} onClick={() => retry(false)}>
                  Retry saving trip
                </ActionButton>
              )}
              {result.saved && (
                <nav className="connected-links" aria-label="Open your trip">
                  <Link className="rt-button rt-button--secondary" to="/trip">
                    Open trip
                  </Link>
                  {result.itinerary && (
                    <Link className="rt-button rt-button--secondary" to="/itinerary">
                      View itinerary
                    </Link>
                  )}
                  <Link to="/trips">Open saved trips</Link>
                </nav>
              )}
            </>
          )}
        </Sheet>
      </main>
    </DesignFrame>
  );
}
