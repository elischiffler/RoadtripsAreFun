import { Link } from 'react-router-dom';
import { DesignFrame, Sheet } from '../design';
import { useRoutingSettings } from '../services/routingSettings';
import './SettingsPage.css';

export default function SettingsPage() {
  const { canSelect } = useRoutingSettings();
  return (
    <DesignFrame className="settings-page">
      <main className="rt-stack">
        <header>
          <p className="rt-caption">Your account</p>
          <h1 className="rt-display">Settings</h1>
        </header>
        <Sheet aria-labelledby="settings-trips">
          <h2 id="settings-trips" className="rt-title">
            Trip planning
          </h2>
          <p className="rt-copy">
            Choose your travel preferences for each trip. Your saved routes and itineraries stay
            together.
          </p>
          <Link className="settings-link" to="/plan">
            Plan a trip <span aria-hidden="true">→</span>
          </Link>
          <Link className="settings-link" to="/trips">
            Saved trips <span aria-hidden="true">→</span>
          </Link>
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
