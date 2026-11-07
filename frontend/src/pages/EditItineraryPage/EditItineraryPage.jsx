import { useContext, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DesignFrame, Sheet, ActionButton } from '../../design';
import Map from '../../components/Map';
import PlaceContext from '../../components/PlaceContext';
import ItineraryDays from '../../components/ItineraryDays';
import { UserDataContext, Data } from '../../states/UserDataContext';
import {
  editedTripSnapshot,
  pendingTripEdit,
  persistTripEdit,
  previewTripEdit,
  reconcileTripEdit,
} from '../../services/tripEdits';
import { loadRouteAlternatives } from '../../services/routeAlternatives';
import { getSession, isCurrentSession } from '../../services/session';
import { useStoredTrip } from '../useStoredTrip';
import './EditItineraryPage.css';

const EditItineraryPage = () => {
  const logs = useStoredTrip();
  const trip = logs?.getChatDataById(logs.currentId) || logs?.chatdata?.[0];
  const { setUserData, chats } = useContext(UserDataContext);
  const [editStatus, setEditStatus] = useState('idle');
  const [editError, setEditError] = useState('');
  const savedNotice = useRef(null);
  const saving = useRef(false);
  const [preview, setPreview] = useState(null);
  const [action, setAction] = useState('add');
  const [stopIndex, setStopIndex] = useState('0');
  const editController = useRef(null);
  const editNumber = useRef(0);
  const active = useRef({ trip, logs });
  active.current = { trip, logs };
  const locked = ['calculating', 'saving', 'uncertain', 'conflict'].includes(editStatus);
  const [ideas, setIdeas] = useState(null);
  const [status, setStatus] = useState('idle');
  const [selectedIdea, setSelectedIdea] = useState(null);
  const controller = useRef(null);
  const mapViewport = useRef(null);
  const requestNumber = useRef(0);
  useEffect(() => {
    controller.current?.abort();
    requestNumber.current += 1;
    setIdeas(null);
    setSelectedIdea(null);
    setStatus('idle');
    setPreview(null);
    setEditStatus(
      pendingTripEdit(logs, trip?.chatId)
        ? 'uncertain'
        : savedNotice.current?.route === trip?.route && savedNotice.current?.id === trip?.chatId
          ? 'saved'
          : 'idle'
    );
    editController.current?.abort();
    editNumber.current += 1;
    return () => {
      controller.current?.abort();
      editController.current?.abort();
      editNumber.current += 1;
      requestNumber.current += 1;
    };
  }, [trip?.chatId, trip?.route, logs]);
  const loadIdeas = async () => {
    controller.current?.abort();
    controller.current = new AbortController();
    const requestId = ++requestNumber.current;
    const session = getSession();
    setStatus('loading');
    setSelectedIdea(null);
    try {
      const result = await loadRouteAlternatives(trip.route, controller.current.signal);
      if (!isCurrentSession(session) || requestId !== requestNumber.current) return;
      setIdeas(result);
      setStatus('ready');
    } catch {
      if (isCurrentSession(session) && requestId === requestNumber.current) setStatus('error');
    }
  };
  const applySaved = (snapshot, original) => {
    if (active.current.trip !== original || active.current.logs !== logs) return;
    savedNotice.current = { id: original.chatId, route: snapshot.route };
    logs.chatdata = logs.chatdata.map((item) =>
      item.chatId === original.chatId ? snapshot : item
    );
    setUserData((current) => (current.chatlogs === logs ? new Data(logs) : current));
    setPreview(null);
    setEditStatus('saved');
  };
  const recalculate = async () => {
    if (locked || preview || !selectedIdea) return;
    const original = trip;
    const session = getSession();
    const number = ++editNumber.current;
    editController.current?.abort();
    editController.current = new AbortController();
    setEditStatus('calculating');
    setEditError('');
    try {
      const result = await previewTripEdit(
        original,
        selectedIdea,
        action,
        Number(stopIndex),
        editController.current.signal
      );
      if (
        !isCurrentSession(session) ||
        active.current.trip !== original ||
        number !== editNumber.current
      )
        return;
      setPreview(result);
      setEditStatus('preview');
    } catch (error) {
      if (
        isCurrentSession(session) &&
        active.current.trip === original &&
        number === editNumber.current
      ) {
        const detail = error.response?.data?.detail;
        setEditError(
          typeof detail === 'string' ? detail.slice(0, 600) : 'Try another place or stop.'
        );
        setEditStatus('error');
      }
    }
  };
  const savePreview = async () => {
    if (!preview || locked || saving.current) return;
    saving.current = true;
    const original = trip;
    const session = getSession();
    setEditStatus('saving');
    const result = await persistTripEdit(
      original,
      editedTripSnapshot(original, preview),
      chats,
      logs,
      session
    );
    saving.current = false;
    if (
      !isCurrentSession(session) ||
      active.current.trip !== original ||
      active.current.logs !== logs
    )
      return;
    if (result.status === 'saved') applySaved(result.snapshot, original);
    else
      setEditStatus(
        result.status === 'unchanged' || result.status === 'unavailable'
          ? 'save-error'
          : result.status
      );
  };
  const checkSaved = async () => {
    const original = trip;
    const session = getSession();
    setEditStatus('saving');
    const result = await reconcileTripEdit(logs, original.chatId, session);
    if (
      !isCurrentSession(session) ||
      active.current.trip !== original ||
      active.current.logs !== logs
    )
      return;
    if (result.status === 'saved') applySaved(result.snapshot, original);
    else setEditStatus(result.status === 'unchanged' ? 'save-error' : result.status);
  };
  return (
    <DesignFrame className="trip-experience edit-itinerary-page">
      {!trip?.route ? (
        <Sheet>
          <h1 className="rt-display">No Route Available</h1>
          <Link to="/trips">Saved trips</Link>
        </Sheet>
      ) : (
        <>
          <header className="rt-stack">
            <h1 className="rt-display">Edit itinerary</h1>
            <Link to="/trip">Back to trip</Link>
          </header>
          <div
            ref={mapViewport}
            tabIndex={-1}
            className="trip-map-viewport"
            aria-label="Trip route map"
          >
            <Map
              key={`${trip.chatId}-${preview ? 'preview' : 'saved'}`}
              UserChatData={preview ? { ...trip, route: preview.route } : trip}
              suggestions={ideas?.places}
              selectedSuggestion={selectedIdea}
              onSelectSuggestion={locked || preview ? undefined : setSelectedIdea}
            />
          </div>
          {editStatus === 'saved' && <p role="status">Trip changes saved.</p>}
          {editStatus === 'uncertain' && (
            <Sheet>
              <p role="alert">
                Save status is uncertain. Changes may already be saved. Check the saved trip before
                making more changes.
              </p>
              <ActionButton onClick={checkSaved}>Check saved trip</ActionButton>
            </Sheet>
          )}
          {editStatus === 'conflict' && (
            <p role="alert">This trip changed or was deleted. Reload saved trips before editing.</p>
          )}
          {selectedIdea && !preview && (
            <Sheet>
              <h2 className="rt-title">{selectedIdea.name}</h2>
              <PlaceContext context={selectedIdea.place_context} />
              <fieldset disabled={locked} className="rt-stack">
                <legend>Change itinerary</legend>
                <label>
                  Action
                  <select
                    value={action}
                    onChange={(event) => {
                      setAction(event.target.value);
                      setStopIndex('');
                    }}
                  >
                    <option value="add">Add before a stop</option>
                    <option value="replace">Replace an attraction</option>
                  </select>
                </label>
                <label>
                  {action === 'add' ? 'Add before' : 'Replace'}
                  <select value={stopIndex} onChange={(event) => setStopIndex(event.target.value)}>
                    <option value="" disabled>
                      Choose a stop
                    </option>
                    {(trip.route.stops || []).map((stop, index) =>
                      action === 'add' || stop.type === 'stop' ? (
                        <option key={index} value={String(index)}>
                          {stop.name || `Stop ${index + 1}`}
                        </option>
                      ) : null
                    )}
                  </select>
                </label>
                <ActionButton
                  disabled={!stopIndex || !(trip.route.stops || []).length}
                  onClick={recalculate}
                >
                  {editStatus === 'calculating' ? 'Recalculating…' : 'Recalculate trip'}
                </ActionButton>
              </fieldset>
              {editStatus === 'error' && (
                <p role="alert">
                  The trip could not be recalculated. {editError} Your saved trip is unchanged.
                </p>
              )}
            </Sheet>
          )}
          {preview && (
            <Sheet>
              <h2 className="rt-title">Review changes</h2>
              <dl className="trip-edit-comparison">
                <dt>Driving time</dt>
                <dd>
                  {Math.round(trip.route.duration / 60)} → {Math.round(preview.route.duration / 60)}{' '}
                  min
                </dd>
                <dt>Distance</dt>
                <dd>
                  {Math.round(trip.route.distance / 1609.344)} →{' '}
                  {Math.round(preview.route.distance / 1609.344)} mi
                </dd>
              </dl>
              {preview.notice && <p className="rt-caption">{preview.notice}</p>}
              <ItineraryDays itinerary={preview.itinerary} />
              <p className="rt-caption">
                Review the updated times. Saved visit checkmarks will be cleared.
              </p>
              <ActionButton disabled={locked} onClick={savePreview}>
                {editStatus === 'saving' ? 'Saving…' : 'Save changes'}
              </ActionButton>
              <ActionButton
                variant="secondary"
                disabled={locked}
                onClick={() => {
                  setPreview(null);
                  setEditStatus('idle');
                }}
              >
                Discard changes
              </ActionButton>
              {editStatus === 'save-error' && (
                <p role="alert">Changes are not saved. Retry saving or discard this preview.</p>
              )}
            </Sheet>
          )}
          <Sheet floating>
            <h2 className="rt-title">Find places along the route</h2>
            <p className="rt-copy">
              Choose a place, recalculate the trip, then review and save your changes.
            </p>
            <ActionButton
              variant="secondary"
              disabled={status === 'loading' || locked || Boolean(preview)}
              onClick={loadIdeas}
            >
              {status === 'loading'
                ? 'Finding places…'
                : status === 'error'
                  ? 'Retry search'
                  : 'Find places'}
            </ActionButton>
            {status === 'loading' && (
              <p className="rt-caption" role="status">
                Searching along the route…
              </p>
            )}
            {status === 'error' && (
              <p className="rt-caption" role="alert">
                Places could not be loaded. Please retry.
              </p>
            )}
            {ideas && (
              <>
                {ideas.notice && <p className="rt-caption">{ideas.notice}</p>}
                {ideas.coverage && !ideas.coverage.continuous && (
                  <p className="rt-caption">
                    Sampled across the route; gaps between searches may remain.
                  </p>
                )}
                {!ideas.places.length && (
                  <p className="rt-copy" role="status">
                    No places found along this route.
                  </p>
                )}
                <ul className="trip-ideas-list">
                  {ideas.places.map((place) => (
                    <li key={place.id}>
                      <h3 className="rt-title">{place.name}</h3>
                      <PlaceContext context={place.place_context} />
                      <ActionButton
                        variant="secondary"
                        aria-label={`View on map: ${place.name}`}
                        disabled={locked || Boolean(preview)}
                        onClick={() => {
                          setSelectedIdea(place);
                          mapViewport.current?.scrollIntoView?.({ block: 'nearest' });
                          mapViewport.current?.focus({ preventScroll: true });
                        }}
                      >
                        View on map
                      </ActionButton>
                      <ActionButton
                        variant="secondary"
                        disabled={locked || Boolean(preview)}
                        onClick={() => setSelectedIdea(place)}
                      >
                        Choose {place.name}
                      </ActionButton>
                      {place.address && <p className="rt-copy">{place.address}</p>}
                      {Number.isFinite(place.offset_miles) && (
                        <p className="rt-caption">
                          {place.offset_miles.toFixed(1)} miles from route sample · driving detour
                          unverified
                        </p>
                      )}
                      {place.url && (
                        <a href={place.url} target="_blank" rel="noopener noreferrer">
                          Place information: {place.name}
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Sheet>
        </>
      )}
    </DesignFrame>
  );
};
export default EditItineraryPage;
