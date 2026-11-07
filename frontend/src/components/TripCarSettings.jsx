import { useContext, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton, ChoiceGroup, Field, Sheet } from '../design';
import { ChatLogs, Data, UserDataContext } from '../states/UserDataContext';
import { initializeUserData } from '../services/savedTrips';
import { getSession, isCurrentSession } from '../services/session';
import { useSessionStatus } from '../services/useSessionStatus';
import { applyTripCar, saveTripCar, tripCarChoices } from '../services/tripCar';

export function TripCarEditor({ trip, onSaved }) {
  const initial = tripCarChoices(trip);
  const [status, setStatus] = useState(initial.car_status);
  const [car, setCar] = useState(initial.car ?? { year: '', make: '', model: '' });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [lifecycle] = useState(() => ({ alive: true }));
  useEffect(() => {
    lifecycle.alive = true;
    return () => {
      lifecycle.alive = false;
    };
  }, [lifecycle]);
  return (
    <form
      className="rt-stack"
      onSubmit={async (event) => {
        event.preventDefault();
        if (busy) return;
        const choices = {
          car_status: status,
          car:
            status === 'provided'
              ? { year: Number(car.year), make: car.make.trim(), model: car.model.trim() }
              : null,
        };
        if (
          choices.car &&
          (!Number.isInteger(choices.car.year) ||
            choices.car.year < 1984 ||
            choices.car.year > 2100 ||
            !choices.car.make ||
            !choices.car.model)
        ) {
          setNotice({ error: true, text: 'Enter a year from 1984 to 2100, car make and model.' });
          return;
        }
        const session = getSession();
        setBusy(true);
        setNotice(null);
        try {
          const saved = await saveTripCar(trip, choices);
          if (!isCurrentSession(session)) return;
          onSaved(trip, saved);
          if (!lifecycle.alive) return;
          setNotice({ text: 'Trip car saved.' });
        } catch (error) {
          if (lifecycle.alive && isCurrentSession(session))
            setNotice({
              error: true,
              text:
                error.response?.status === 404
                  ? 'This trip changed or was deleted. Reload before editing.'
                  : 'Car settings could not be saved. Your changes are kept; retry saving.',
            });
        } finally {
          if (lifecycle.alive && isCurrentSession(session)) setBusy(false);
        }
      }}
    >
      {notice && <p role={notice.error ? 'alert' : 'status'}>{notice.text}</p>}
      <fieldset className="settings-fields rt-stack" disabled={busy}>
        <legend>Car details</legend>
        <ChoiceGroup
          legend="Car for this trip"
          value={status}
          onChange={setStatus}
          options={[
            { value: 'skipped', label: 'No car details' },
            { value: 'provided', label: 'Use this car' },
          ]}
        />
        {status === 'provided' &&
          ['year', 'make', 'model'].map((key) => (
            <Field
              key={key}
              label={'Car ' + key}
              type={key === 'year' ? 'number' : 'text'}
              {...(key === 'year' ? { min: 1984, max: 2100, step: 1 } : { maxLength: 100 })}
              required
              value={car[key]}
              onChange={(event) => setCar((old) => ({ ...old, [key]: event.target.value }))}
            />
          ))}
      </fieldset>
      <p className="rt-caption">
        Applies to this trip. Any previous fuel estimate is cleared; reusable profiles stay
        unchanged.
      </p>
      <ActionButton type="submit" disabled={busy}>
        {busy ? 'Saving car…' : 'Save trip car'}
      </ActionButton>
    </form>
  );
}
TripCarEditor.propTypes = { trip: PropTypes.object.isRequired, onSaved: PropTypes.func.isRequired };

export default function TripCarSettings() {
  const { UserData, setUserData, chats, setChats } = useContext(UserDataContext);
  const session = useSessionStatus();
  const [selection, setSelection] = useState(null);
  const [load, setLoad] = useState({ owner: null, status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const logs = UserData.chatlogs;
  const tripCount = logs.chatdata.length;
  useEffect(() => {
    let alive = true;
    const started = getSession();
    if (tripCount) {
      setLoad({ owner: started.owner, status: 'ready' });
      return;
    }
    if (!started.owner) return;
    setLoad({ owner: started.owner, status: 'loading' });
    initializeUserData(started.accessToken).then((result) => {
      if (!alive || !isCurrentSession(started)) return;
      if (!result) {
        setLoad({ owner: started.owner, status: 'error' });
        return;
      }
      setLoad({ owner: started.owner, status: 'ready' });
      // Do not replace trip context: another view may have selected or edited it
      // while this read was in flight. Only fill an empty context.
      setUserData((previous) => (previous.chatlogs.chatdata.length ? previous : result.UserData));
      setChats((previous) => (previous.length ? previous : result.chats));
    });
    return () => {
      alive = false;
    };
  }, [tripCount, session.owner, attempt, setUserData, setChats]);
  const id = selection?.owner === session.owner ? selection.id : logs.currentId;
  const trip = logs.getChatDataById(id) ?? logs.chatdata[0];
  return (
    <Sheet aria-labelledby="settings-trip-car">
      <h2 id="settings-trip-car" className="rt-title">
        Trip car
      </h2>
      {load.owner !== session.owner || load.status === 'loading' ? (
        <p role="status">Loading trip cars…</p>
      ) : load.status === 'error' ? (
        <>
          <p role="status">Saved trips could not be loaded.</p>
          <ActionButton variant="secondary" onClick={() => setAttempt((value) => value + 1)}>
            Retry loading trip cars
          </ActionButton>
        </>
      ) : !trip ? (
        <p className="rt-caption">Save a trip to add its car details.</p>
      ) : (
        <>
          <label className="rt-field__label" htmlFor="car-trip-select">
            Trip
          </label>
          <select
            id="car-trip-select"
            className="rt-input"
            value={trip.chatId}
            onChange={(event) =>
              setSelection({ owner: session.owner, id: Number(event.target.value) })
            }
          >
            {logs.chatdata.map((item) => (
              <option key={item.chatId} value={item.chatId}>
                {chats.find((record) => record.id === item.chatId)?.title ||
                  [item.tripProfile?.start_address, item.tripProfile?.destination_address]
                    .filter(Boolean)
                    .join(' → ') ||
                  `Trip ${item.chatId}`}
              </option>
            ))}
          </select>
          <TripCarEditor
            key={`${session.owner}:${trip.chatId}:${trip.agentChatId ?? ''}`}
            trip={trip}
            onSaved={(original, choices) => {
              setUserData(
                (previous) =>
                  new Data(
                    new ChatLogs(
                      previous.chatlogs.chatdata.map((item) =>
                        item.chatId === original.chatId && item.agentChatId === original.agentChatId
                          ? applyTripCar(item, choices)
                          : item
                      ),
                      previous.chatlogs.currentId
                    )
                  )
              );
            }}
          />
        </>
      )}
    </Sheet>
  );
}
