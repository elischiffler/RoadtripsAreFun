import { useNavigate } from 'react-router-dom';
import './LogoButton.css';

/** Shared home control. The same vector mark is also the browser favicon. */
export default function LogoButton() {
  const navigate = useNavigate();

  return (
    <button
      type="button"
      className="logo-btn"
      onClick={() => navigate('/')}
      aria-label="RoadtripsAreFun home"
    >
      <img
        className="logo-image"
        src="/favicon.svg"
        width="40"
        height="40"
        alt=""
        aria-hidden="true"
        draggable="false"
      />
    </button>
  );
}
