import PropTypes from 'prop-types';
import { useRef } from 'react';

export default function TripPresetDialog({ catalog, presetId, disabled, onSelect }) {
  const dialog = useRef(null);
  const selected = catalog.presets.find((preset) => preset.id === presetId);
  const endpointLabel = (id) => catalog.endpoints.find((endpoint) => endpoint.id === id)?.label;
  return (
    <>
      <div className="lab-preset-trigger">
        <button
          type="button"
          disabled={disabled}
          aria-haspopup="dialog"
          onClick={() => dialog.current.showModal()}
        >
          Trip presets
        </button>
        <span>Selected trip: {selected?.label}</span>
      </div>
      <dialog ref={dialog} className="lab-preset-dialog" aria-labelledby="trip-presets-title">
        <div className="lab-preset-heading">
          <h2 id="trip-presets-title">Choose a trip preset</h2>
          <button type="button" onClick={() => dialog.current.close()}>
            Close presets
          </button>
        </div>
        <p className="lab-note">
          Pick a trip to fill every field. You can edit the details before running it with live
          providers.
        </p>
        <div className="lab-preset-grid">
          {catalog.presets.map((preset) => (
            <button
              type="button"
              className="lab-preset-card"
              key={preset.id}
              aria-pressed={presetId === preset.id}
              onClick={() => {
                onSelect(preset.id);
                dialog.current.close();
              }}
            >
              <strong>{preset.label}</strong>
              <span>
                {endpointLabel(preset.inputs.start_id)} →{' '}
                {endpointLabel(preset.inputs.destination_id)}
              </span>
              <small>
                {preset.inputs.traveler_count} traveler(s) · {preset.inputs.num_stops} attractions
                {' · $'}
                {preset.inputs.budget}/room/night
              </small>
              {preset.description && <small>{preset.description}</small>}
            </button>
          ))}
        </div>
      </dialog>
    </>
  );
}

TripPresetDialog.propTypes = {
  catalog: PropTypes.shape({
    presets: PropTypes.arrayOf(PropTypes.object).isRequired,
    endpoints: PropTypes.arrayOf(PropTypes.object).isRequired,
  }).isRequired,
  presetId: PropTypes.string.isRequired,
  disabled: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
};
