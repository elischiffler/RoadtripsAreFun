import { Link } from 'react-router-dom';
import './HomePage.css';

export default function HomePage() {
  return (
    <main className="home-page">
      <div className="home-copy">
        <p className="home-eyebrow">RoadtripsAreFun</p>
        <h1>The journey is part of the trip.</h1>
        <p>Find the stops you’ll love. Make a little room for discovery.</p>
      </div>
      <nav className="home-destinations" aria-label="Choose your workspace">
        <Link className="home-destination home-destination--plan" to="/plan">
          <span className="home-card-number" aria-hidden="true">
            01
          </span>
          <h2>Plan a trip</h2>
          <p>A few simple steps, your favorite kinds of places, and a route that fits.</p>
          <span className="home-card-action">
            Let’s get started{' '}
            <svg
              aria-hidden="true"
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M5 15 15 5M5 5h10v10" />
            </svg>
          </span>
        </Link>
        <Link className="home-destination" to="/studio">
          <span className="home-card-number" aria-hidden="true">
            02
          </span>
          <h2>AI Studio</h2>
          <p>Explore trip inputs, compare measured runs, and see how the planner works.</p>
          <span className="home-card-action">
            Open the research workspace{' '}
            <svg
              aria-hidden="true"
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M5 15 15 5M5 5h10v10" />
            </svg>
          </span>
        </Link>
      </nav>
      <p className="home-saved">
        <Link to="/trips">Open saved trips</Link>
        <span> · </span> Your saved routes and itineraries stay together.
      </p>
    </main>
  );
}
