import { useState } from 'react';
import PropTypes from 'prop-types';
import { ActionButton, ChoiceGroup, Field } from '../design';
import { INTERESTS, newSetupDraft, setupErrors } from '../pages/TripSetup/setupModel';
import { applyPreferenceChoices, choicesFromDraft } from '../services/preferenceProfiles';

const TIMES = {
  morning_restart: 'Start driving each morning',
  preferred_hotel_arrival: 'Preferred hotel arrival',
  latest_hotel_arrival: 'Latest hotel arrival',
  latest_destination_arrival: 'Latest destination arrival',
  late_cutoff: 'Late driving cutoff',
};
export default function PreferenceProfileEditor({ profile, onSave, onCancel, busy }) {
  const [id] = useState(() => profile?.id ?? crypto.randomUUID());
  const [name, setName] = useState(profile?.name ?? '');
  const [draft, setDraft] = useState(() =>
    profile
      ? applyPreferenceChoices(newSetupDraft(), profile.choices)
      : { ...newSetupDraft(), carStatus: 'skipped' }
  );
  const [error, setError] = useState('');
  const set = (key, value) => setDraft((old) => ({ ...old, [key]: value }));
  return (
    <form
      className="rt-stack"
      onSubmit={(event) => {
        event.preventDefault();
        const errors = { ...setupErrors(draft, 2), ...setupErrors(draft, 3) };
        if (
          !(
            draft.schedule.morning_restart < draft.schedule.preferred_hotel_arrival &&
            draft.schedule.preferred_hotel_arrival <= draft.schedule.latest_hotel_arrival &&
            draft.schedule.latest_hotel_arrival <= draft.schedule.late_cutoff
          )
        )
          errors.schedule =
            'Morning start must be before hotel arrival, and latest arrival must be before the late cutoff.';
        if (!name.trim()) errors.name = 'Enter a profile name.';
        if (Object.keys(errors).length) {
          setError(Object.values(errors).join(' '));
          return;
        }
        try {
          void onSave({
            id,
            name: name.trim(),
            choices: choicesFromDraft(draft),
          });
        } catch (failure) {
          setError(failure.message);
        }
      }}
    >
      <h3 className="rt-title">{profile ? 'Edit preferences' : 'New preferences'}</h3>
      {error && <p role="alert">{error}</p>}
      <fieldset disabled={busy} className="settings-fields rt-stack">
        <legend>Profile details</legend>
        <Field
          label="Profile name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={80}
          required
        />
        <ChoiceGroup
          legend="Car"
          value={draft.carStatus}
          onChange={(value) => {
            setDraft((old) => ({
              ...old,
              carStatus: value,
              ...(value === 'skipped' ? { year: '', make: '', model: '' } : {}),
            }));
          }}
          options={[
            { value: 'skipped', label: 'No car details' },
            { value: 'provided', label: 'Use this car' },
          ]}
        />
        {draft.carStatus === 'provided' && (
          <div className="rt-stack">
            <Field
              label="Car year"
              type="number"
              min={1984}
              max={2100}
              value={draft.year}
              onChange={(event) => set('year', event.target.value)}
              required
            />
            <Field
              label="Car make"
              value={draft.make}
              maxLength={100}
              onChange={(event) => set('make', event.target.value)}
              required
            />
            <Field
              label="Car model"
              value={draft.model}
              maxLength={100}
              onChange={(event) => set('model', event.target.value)}
              required
            />
          </div>
        )}
        <h4 className="rt-title">Daily timing</h4>
        {Object.entries(TIMES).map(([key, label]) => (
          <Field
            key={key}
            label={label}
            type={key === 'late_cutoff' ? 'text' : 'time'}
            hint={key === 'late_cutoff' ? 'HH:MM; use 24:00 for midnight.' : undefined}
            value={draft.schedule[key]}
            onChange={(event) => set('schedule', { ...draft.schedule, [key]: event.target.value })}
          />
        ))}
        <label className="settings-check">
          <input
            type="checkbox"
            checked={draft.schedule.late_driving}
            onChange={(event) =>
              set('schedule', { ...draft.schedule, late_driving: event.target.checked })
            }
          />
          Allow late driving
        </label>
        <details>
          <summary>Interests</summary>
          <p className="rt-caption">
            Editable weights from your chosen trip preferences. No inferred account personality is
            included.
          </p>
          {draft.customWeights ? (
            <div className="rt-stack">
              {Object.entries(INTERESTS).map(([key, label]) => (
                <Field
                  key={key}
                  label={label}
                  type="number"
                  min={0}
                  step="any"
                  value={draft.customWeights[key]}
                  onChange={(event) =>
                    set('customWeights', {
                      ...draft.customWeights,
                      [key]: Number(event.target.value),
                    })
                  }
                />
              ))}
            </div>
          ) : (
            Object.entries(INTERESTS).map(([key, label]) => (
              <label className="settings-check" key={key}>
                <input
                  type="checkbox"
                  checked={draft.interests.includes(key)}
                  onChange={(event) =>
                    set(
                      'interests',
                      event.target.checked
                        ? [...draft.interests, key]
                        : draft.interests.filter((item) => item !== key)
                    )
                  }
                />
                {label}
              </label>
            ))
          )}
        </details>
      </fieldset>
      <div className="settings-actions">
        <ActionButton type="submit" disabled={busy}>
          Save preferences
        </ActionButton>
        <ActionButton variant="secondary" disabled={busy} onClick={onCancel}>
          Cancel
        </ActionButton>
      </div>
    </form>
  );
}
PreferenceProfileEditor.propTypes = {
  profile: PropTypes.object,
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  busy: PropTypes.bool,
};
