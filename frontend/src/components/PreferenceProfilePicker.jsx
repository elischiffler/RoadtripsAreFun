import { useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton } from '../design';
import usePreferenceProfiles from '../services/usePreferenceProfiles';
import { applyPreferenceChoices } from '../services/preferenceProfiles';

export default function PreferenceProfilePicker({ setDraft, disabled = false }) {
  const { profiles, loading, error, refresh } = usePreferenceProfiles();
  const [selected, setSelected] = useState('');
  const [message, setMessage] = useState('');
  const [loaded, setLoaded] = useState(false);
  const panel = useRef(null);
  const trigger = useRef(null);
  if (loading)
    return (
      <p role="status" className="rt-caption">
        Loading preferences…
      </p>
    );
  if (error)
    return (
      <div>
        <p role="status" className="rt-caption">
          {error} You can enter new choices.
        </p>
        <ActionButton variant="secondary" onClick={refresh}>
          Retry preferences
        </ActionButton>
      </div>
    );
  if (!profiles.length && !message) return null;
  return (
    <>
      <details className="setup-preference-picker" ref={panel}>
        <summary ref={trigger}>Use saved preferences</summary>
        <div className="rt-stack">
          <label className="rt-field__label" htmlFor="reuse-preferences">
            Saved preferences
          </label>
          {profiles.length ? (
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
                    setMessage('');
                    setLoaded(true);
                    panel.current.open = false;
                    trigger.current?.focus({ preventScroll: true });
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
          ) : null}
          <ActionButton
            variant="secondary"
            onClick={() => {
              panel.current.open = false;
              trigger.current?.focus({ preventScroll: true });
            }}
          >
            Done choosing preferences
          </ActionButton>
          {message && (
            <p role="status" className="rt-caption">
              {message}
            </p>
          )}
        </div>
      </details>
      {loaded && (
        <p role="status" className="rt-caption">
          Preferences loaded.
        </p>
      )}
    </>
  );
}
PreferenceProfilePicker.propTypes = {
  setDraft: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
