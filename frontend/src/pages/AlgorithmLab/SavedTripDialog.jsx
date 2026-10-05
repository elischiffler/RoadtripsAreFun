import PropTypes from 'prop-types';
import { useEffect, useRef, useState } from 'react';
import { getLabResult, labError } from '../../services/algorithmLab';
import Map from '../../components/Map';
import ItineraryDays from '../../components/ItineraryDays';

export default function SavedTripDialog({ run, onClose }) {
  const dialog = useRef(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    dialog.current.showModal();
    getLabResult(run.id, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResult(data);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(labError(failure));
      });
    return () => controller.abort();
  }, [run.id]);
  const geometry = result?.route?.geometry?.coordinates;
  return (
    <dialog
      ref={dialog}
      className="lab-saved-trip-dialog"
      aria-labelledby="saved-trip-title"
      onCancel={onClose}
    >
      <div className="lab-preset-heading">
        <h2 id="saved-trip-title">Map and itinerary · {run.preset_id}</h2>
        <button type="button" onClick={onClose}>
          Close trip
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {!result && !error && <p role="status">Loading saved trip…</p>}
      {result && (
        <>
          {geometry?.length > 1 && (
            <div className="lab-map">
              <Map
                UserChatData={{
                  route: result.route,
                  startConfirmed: { longitude: geometry[0][0], latitude: geometry[0][1] },
                  endConfirmed: { longitude: geometry.at(-1)[0], latitude: geometry.at(-1)[1] },
                }}
              />
            </div>
          )}
          <ol className="lab-route-stops">
            {result.route.stops?.map((stop, index) => (
              <li key={index}>{stop.name}</li>
            ))}
          </ol>
          {result.route.warnings?.map((warning, index) => (
            <p className="lab-warning" key={index}>
              {warning}
            </p>
          ))}
          {result.itinerary?.length ? (
            <div className="lab-itinerary">
              <ItineraryDays itinerary={result.itinerary} />
            </div>
          ) : (
            <p>Route saved; itinerary generation did not finish.</p>
          )}
        </>
      )}
    </dialog>
  );
}
SavedTripDialog.propTypes = {
  run: PropTypes.object.isRequired,
  onClose: PropTypes.func.isRequired,
};
