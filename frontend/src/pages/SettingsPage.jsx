import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ActionButton, ChoiceGroup, DesignFrame, Sheet } from '../design';
import { useRoutingSettings } from '../services/routingSettings';
import { useSessionStatus } from '../services/useSessionStatus';
import { getSession, isCurrentSession } from '../services/session';
import { useThemeMode, setThemeMode } from '../services/themeMode';
import usePreferenceProfiles from '../services/usePreferenceProfiles';
import { savePreferenceProfile, deletePreferenceProfile } from '../services/preferenceProfiles';
import PreferenceProfileEditor from '../components/PreferenceProfileEditor';
import './SettingsPage.css';

export default function SettingsPage() {
  const { canSelect } = useRoutingSettings();
  useSessionStatus();
  const owner = getSession().owner;
  const mode = useThemeMode();
  const { profiles, loading, error, refresh } = usePreferenceProfiles();
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  useEffect(() => {
    setEditing(null);
    setDeleting(null);
    setNotice(null);
    setBusy(false);
  }, [owner]);
  const activeEditor = editing?.owner === owner ? editing.profile : null;
  const perform = async (operation, message) => {
    const session = getSession();
    setBusy(true);
    setNotice(null);
    try {
      await operation();
      if (!isCurrentSession(session)) return;
      setEditing(null);
      setDeleting(null);
      setNotice({ owner, message });
      refresh();
    } catch {
      if (isCurrentSession(session))
        setNotice({ owner, message: 'Could not save this change. Please retry.', error: true });
    } finally {
      if (isCurrentSession(session)) setBusy(false);
    }
  };
  return (
    <DesignFrame className="settings-page">
      <main className="rt-stack">
        <header>
          <h1 className="rt-display">Settings</h1>
        </header>
        <Sheet aria-labelledby="settings-appearance">
          <h2 id="settings-appearance" className="rt-title">
            Appearance
          </h2>
          <ChoiceGroup
            legend="Theme"
            description="Saved on this browser."
            value={mode}
            onChange={setThemeMode}
            options={[
              { value: 'light', label: 'Light' },
              { value: 'dark', label: 'Dark' },
            ]}
          />
        </Sheet>
        <Sheet aria-labelledby="settings-preferences">
          <h2 id="settings-preferences" className="rt-title">
            Trip preferences
          </h2>
          <p className="rt-copy">
            Reuse your car, daily timing and interests. New preference sets are saved with each
            trip. Choose one when starting another trip.
          </p>
          <p className="rt-caption">
            Locations, departure date, stops and travelers are entered for each trip. Editing or
            deleting a profile leaves saved trips unchanged.
          </p>
          {notice?.owner === owner && (
            <p role={notice.error ? 'alert' : 'status'}>{notice.message}</p>
          )}
          {loading ? (
            <p role="status">Loading preferences…</p>
          ) : error ? (
            <div>
              <p role="status">{error}</p>
              <ActionButton variant="secondary" onClick={refresh}>
                Retry loading preferences
              </ActionButton>
            </div>
          ) : (
            <ul className="settings-profiles">
              {profiles.map((profile) => (
                <li key={profile.id} className="rt-stack">
                  <h3 className="rt-title">{profile.name}</h3>
                  <p className="rt-caption">
                    {profile.choices.car
                      ? `${profile.choices.car.year} ${profile.choices.car.make} ${profile.choices.car.model}`
                      : 'No car details'}{' '}
                    · Start {profile.choices.scheduling_policy.morning_restart} · Hotel{' '}
                    {profile.choices.scheduling_policy.preferred_hotel_arrival}
                  </p>
                  {deleting?.owner === owner && deleting.id === profile.id ? (
                    <div className="rt-stack">
                      <p>Delete “{profile.name}” from saved preferences?</p>
                      <div className="settings-actions">
                        <ActionButton
                          disabled={busy}
                          onClick={() =>
                            perform(
                              () => deletePreferenceProfile(profile.id),
                              'Preferences deleted.'
                            )
                          }
                        >
                          Confirm delete
                        </ActionButton>
                        <ActionButton
                          variant="secondary"
                          disabled={busy}
                          onClick={() => setDeleting(null)}
                        >
                          Keep profile
                        </ActionButton>
                      </div>
                    </div>
                  ) : (
                    <div className="settings-actions">
                      <ActionButton
                        variant="secondary"
                        disabled={busy}
                        onClick={() => {
                          setEditing({ owner, profile });
                          setDeleting(null);
                        }}
                      >
                        Edit {profile.name}
                      </ActionButton>
                      <ActionButton
                        variant="secondary"
                        disabled={busy}
                        onClick={() => {
                          setDeleting({ owner, id: profile.id });
                          setEditing(null);
                        }}
                      >
                        Delete {profile.name}
                      </ActionButton>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
          {!loading && !error && !profiles.length && (
            <p className="rt-caption">No saved preferences yet.</p>
          )}
          {activeEditor ? (
            <PreferenceProfileEditor
              key={activeEditor.id ?? 'new'}
              profile={activeEditor.id ? activeEditor : undefined}
              busy={busy}
              onCancel={() => setEditing(null)}
              onSave={(profile) =>
                perform(() => savePreferenceProfile(profile), 'Preferences saved.')
              }
            />
          ) : (
            <ActionButton
              variant="secondary"
              disabled={busy || !owner}
              onClick={() => {
                setEditing({ owner, profile: {} });
                setDeleting(null);
              }}
            >
              New preferences
            </ActionButton>
          )}
        </Sheet>
        {canSelect && (
          <Sheet aria-labelledby="settings-research">
            <h2 id="settings-research" className="rt-title">
              Research workspace
            </h2>
            <Link className="settings-link" to="/studio">
              AI Studio <span aria-hidden="true">→</span>
            </Link>
            <Link className="settings-link" to="/studio/research">
              Trip research <span aria-hidden="true">→</span>
            </Link>
          </Sheet>
        )}
      </main>
    </DesignFrame>
  );
}
