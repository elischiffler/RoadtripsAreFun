import { useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton } from '../design';
import usePreferenceProfiles from '../services/usePreferenceProfiles';
import { applyPreferenceChoices } from '../services/preferenceProfiles';

export default function PreferenceProfilePicker({ setDraft, disabled = false }) {
  const { profiles, loading, error, refresh } = usePreferenceProfiles();
  const [selected, setSelected] = useState('');
  const [message, setMessage] = useState('');
  return (
    <div className="rt-stack">
      <label className="rt-field__label" htmlFor="reuse-preferences">
        Saved preferences
      </label>
      <p className="rt-caption">
        Reuse your car, timing and interests. Review them before planning.
      </p>
      {loading ? (
        <p role="status">Loading preferences…</p>
      ) : error ? (
        <div>
          <p role="status">{error} You can enter new choices.</p>
          <ActionButton variant="secondary" onClick={refresh}>
            Retry preferences
          </ActionButton>
        </div>
      ) : profiles.length ? (
        <>
          <select
            id="reuse-preferences"
            className="rt-input"
            value={selected}
            disabled={disabled}
            onChange={(event) => {
              setSelected(event.target.value);
              setMessage('');
            }}
          >
            <option value="">Choose a profile</option>
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
              </option>
            ))}
          </select>
          <ActionButton
            variant="secondary"
            disabled={disabled || !profiles.some((profile) => profile.id === selected)}
            onClick={() => {
              try {
                const profile = profiles.find((item) => item.id === selected);
                setDraft((draft) => applyPreferenceChoices(draft, profile.choices));
                setMessage(
                  'Preferences loaded. Your trip locations, date and stops are unchanged.'
                );
              } catch {
                setMessage(
                  'This profile could not be loaded. Enter new choices or choose another.'
                );
              }
            }}
          >
            Load preferences
          </ActionButton>
        </>
      ) : (
        <p className="rt-caption">New preference sets are saved when you save a trip.</p>
      )}
      {message && (
        <p role="status" className="rt-caption">
          {message}
        </p>
      )}
    </div>
  );
}
PreferenceProfilePicker.propTypes = {
  setDraft: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
