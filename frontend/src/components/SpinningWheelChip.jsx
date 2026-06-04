import { Box } from '@mui/material';
import './SpinningWheelChip.css';

/**
 * SpinningWheelChip
 *
 * On hover the pill morphs into a circle and the label text
 * rotates around the rim like a wheel spinning forward.
 */
export default function SpinningWheelChip({ label, icon }) {
  // Repeat label around the full circle with bullet separators
  const repeated = `${label} · ${label} · ${label} · `;
  const R = 36; // circle radius
  const cx = 44;
  const cy = 44;
  const circleD = 2 * Math.PI * R; // circumference ≈ 226

  return (
    <Box className="swc-wrapper">
      {/* ── Resting pill state ── */}
      <Box className="swc-pill">
        <span className="swc-pill-icon">{icon}</span>
        <span className="swc-pill-label">{label}</span>
      </Box>

      {/* ── Hover wheel state ── */}
      <Box className="swc-wheel" aria-hidden="true">
        <svg width="88" height="88" viewBox="0 0 88 88" className="swc-svg">
          {/* Spoke cross */}
          <line x1={cx} y1={cy - R} x2={cx} y2={cy + R} className="swc-spoke" />
          <line x1={cx - R} y1={cy} x2={cx + R} y2={cy} className="swc-spoke" />
          <line
            x1={cx - R * 0.707}
            y1={cy - R * 0.707}
            x2={cx + R * 0.707}
            y2={cy + R * 0.707}
            className="swc-spoke"
          />
          <line
            x1={cx + R * 0.707}
            y1={cy - R * 0.707}
            x2={cx - R * 0.707}
            y2={cy + R * 0.707}
            className="swc-spoke"
          />

          {/* Hub */}
          <circle cx={cx} cy={cy} r="5" className="swc-hub" />

          {/* Rim */}
          <circle cx={cx} cy={cy} r={R} className="swc-rim" />

          {/* Circular text path */}
          <defs>
            <path
              id="swc-text-circle"
              d={`
                M ${cx - R} ${cy}
                a ${R} ${R} 0 1 1 ${R * 2} 0
                a ${R} ${R} 0 1 1 ${-R * 2} 0
              `}
            />
          </defs>
          <text className="swc-rim-text">
            <textPath href="#swc-text-circle" startOffset="0%">
              {repeated}
            </textPath>
          </text>
        </svg>
      </Box>
    </Box>
  );
}
