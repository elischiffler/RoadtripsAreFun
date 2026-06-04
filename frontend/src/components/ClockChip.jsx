import { useState, useEffect, useRef } from 'react';
import { Box } from '@mui/material';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import './ClockChip.css';

// Tick the clock forward — each tick advances the angle
// The clock cycles: fast spin → slow → reverse fast → slow → repeat
const CYCLE_MS = 2800; // full forward+backward cycle duration

export default function ClockChip({ label }) {
  const [active, setActive] = useState(false);
  const [hourAngle, setHourAngle] = useState(0);
  const [minAngle, setMinAngle] = useState(0);
  const rafRef = useRef(null);
  const startRef = useRef(null);

  const animate = (timestamp) => {
    if (!startRef.current) startRef.current = timestamp;

    // Position within a single forward+backward cycle (0 → CYCLE_MS*2)
    const elapsed = (timestamp - startRef.current) % (CYCLE_MS * 2);

    // Map elapsed to a continuous angle using a sine wave:
    // sin goes 0→1→0→-1→0 over a full period, giving smooth forward+reverse
    // We want: start at 0, peak at +MAX, return to 0, no teleport
    const progress = (elapsed / (CYCLE_MS * 2)) * Math.PI * 2; // 0 → 2π
    // Use (1 - cos) / 2 to get a 0→1→0 envelope, then multiply by full rotations
    const envelope = (1 - Math.cos(progress)) / 2; // 0 → 1 → 0, smooth

    const MAX_MIN_DEG = 720; // 2 full rotations forward at peak
    const MAX_HOUR_DEG = 60; // proportional hour hand

    setMinAngle(envelope * MAX_MIN_DEG);
    setHourAngle(envelope * MAX_HOUR_DEG);

    rafRef.current = requestAnimationFrame(animate);
  };

  const handleEnter = () => {
    setActive(true);
    startRef.current = null;
    rafRef.current = requestAnimationFrame(animate);
  };

  const handleLeave = () => {
    setActive(false);
    cancelAnimationFrame(rafRef.current);
    setHourAngle(0);
    setMinAngle(0);
    startRef.current = null;
  };

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  const R = 34; // clock radius
  const cx = 44;
  const cy = 44;

  // Hand tip coordinates from angle (0 = 12 o'clock = up = -90° offset)
  const handPoint = (angle, length) => ({
    x: cx + Math.sin((angle * Math.PI) / 180) * length,
    y: cy - Math.cos((angle * Math.PI) / 180) * length,
  });

  const hourTip = handPoint(hourAngle, R * 0.55);
  const minTip = handPoint(minAngle, R * 0.8);

  // Hour markers
  const markers = Array.from({ length: 12 }, (_, i) => {
    const a = (i / 12) * 360;
    const isQt = i % 3 === 0;
    const inner = R * (isQt ? 0.75 : 0.85);
    const outer = R * 0.95;
    return {
      x1: cx + Math.sin((a * Math.PI) / 180) * inner,
      y1: cy - Math.cos((a * Math.PI) / 180) * inner,
      x2: cx + Math.sin((a * Math.PI) / 180) * outer,
      y2: cy - Math.cos((a * Math.PI) / 180) * outer,
      isQt,
    };
  });

  return (
    <Box className="clock-chip-wrapper" onMouseEnter={handleEnter} onMouseLeave={handleLeave}>
      {/* ── Resting pill ── */}
      <Box className={`clock-pill ${active ? 'clock-pill--hidden' : ''}`}>
        <span className="clock-pill-icon">
          <CalendarMonthIcon fontSize="small" />
        </span>
        <span className="clock-pill-label">{label}</span>
      </Box>

      {/* ── Clock ── */}
      <Box className={`clock-face ${active ? 'clock-face--visible' : ''}`}>
        <svg width="88" height="88" viewBox="0 0 88 88">
          {/* Outer ring */}
          <circle cx={cx} cy={cy} r={R} className="clock-rim" />
          {/* Inner fill */}
          <circle cx={cx} cy={cy} r={R - 2} className="clock-bg" />

          {/* Hour markers */}
          {markers.map((m, i) => (
            <line
              key={i}
              x1={m.x1}
              y1={m.y1}
              x2={m.x2}
              y2={m.y2}
              className={m.isQt ? 'clock-marker-qt' : 'clock-marker'}
            />
          ))}

          {/* Hour hand */}
          <line x1={cx} y1={cy} x2={hourTip.x} y2={hourTip.y} className="clock-hand-hour" />

          {/* Minute hand */}
          <line x1={cx} y1={cy} x2={minTip.x} y2={minTip.y} className="clock-hand-min" />

          {/* Centre pin */}
          <circle cx={cx} cy={cy} r="3" className="clock-pin" />
        </svg>
      </Box>
    </Box>
  );
}
