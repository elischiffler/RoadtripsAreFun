import { useNavigate } from "react-router-dom";
import { Box } from "@mui/material";
import "./LogoButton.css";

export default function LogoButton() {
  const navigate = useNavigate();

  return (
    <Box
      className="logo-btn"
      onClick={() => navigate("/")}
      role="button"
      aria-label="Go to home"
    >
      <svg
        className="logo-svg"
        width="64"
        height="40"
        viewBox="0 0 64 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* ── Mountain ── */}
        <polygon
          points="10,32 24,10 38,32"
          className="logo-mountain logo-mountain--back"
        />
        <polygon
          points="28,32 44,14 60,32"
          className="logo-mountain logo-mountain--front"
        />

        {/* ── Scrolling road (clipped) ── */}
        <clipPath id="road-clip">
          <rect x="0" y="28" width="64" height="12" />
        </clipPath>
        <g clipPath="url(#road-clip)">
          {/* Road surface */}
          <rect x="0" y="30" width="64" height="6" className="logo-road" />
          {/* Dashed centre line — two copies side by side so the scroll loops */}
          <g className="logo-road-dashes">
            <rect x="2"  y="32" width="8" height="2" rx="1" className="logo-dash" />
            <rect x="18" y="32" width="8" height="2" rx="1" className="logo-dash" />
            <rect x="34" y="32" width="8" height="2" rx="1" className="logo-dash" />
            <rect x="50" y="32" width="8" height="2" rx="1" className="logo-dash" />
            {/* duplicate set offset by 64px for seamless loop */}
            <rect x="66" y="32" width="8" height="2" rx="1" className="logo-dash" />
            <rect x="82" y="32" width="8" height="2" rx="1" className="logo-dash" />
            <rect x="98" y="32" width="8" height="2" rx="1" className="logo-dash" />
            <rect x="114" y="32" width="8" height="2" rx="1" className="logo-dash" />
          </g>
        </g>

        {/* ── Car body ── */}
        {/* Main chassis */}
        <rect x="10" y="22" width="28" height="8" rx="2" className="logo-car-body" />
        {/* Cabin */}
        <rect x="16" y="16" width="16" height="8" rx="2" className="logo-car-cabin" />
        {/* Windshields */}
        <rect x="17" y="17" width="6" height="6" rx="1" className="logo-window" />
        <rect x="25" y="17" width="6" height="6" rx="1" className="logo-window" />
        {/* Bumper detail */}
        <rect x="36" y="24" width="3" height="3" rx="1" className="logo-bumper" />
        {/* Headlight */}
        <rect x="37" y="24" width="2" height="2" rx="0.5" className="logo-headlight" />

        {/* ── Wheels (spin on hover) ── */}
        {/* Rear wheel */}
        <circle cx="17" cy="31" r="4" className="logo-wheel" />
        <circle cx="17" cy="31" r="1.2" className="logo-hub" />
        <line x1="17" y1="27.2" x2="17" y2="34.8" className="logo-spoke logo-spoke--rear" />
        <line x1="13.2" y1="31" x2="20.8" y2="31" className="logo-spoke logo-spoke--rear" />

        {/* Front wheel */}
        <circle cx="31" cy="31" r="4" className="logo-wheel" />
        <circle cx="31" cy="31" r="1.2" className="logo-hub" />
        <line x1="31" y1="27.2" x2="31" y2="34.8" className="logo-spoke logo-spoke--front" />
        <line x1="27.2" y1="31" x2="34.8" y2="31" className="logo-spoke logo-spoke--front" />
      </svg>
    </Box>
  );
}
