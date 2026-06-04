import { useState, useEffect, useRef } from "react";
import { Box, Typography } from "@mui/material";
import HotelIcon from "@mui/icons-material/Hotel";
import "./HotelChip.css";

const COLS = 5;
const ROWS = 6;
const TOTAL = COLS * ROWS;

// Schedule a window to toggle on/off indefinitely
function scheduleWindow(idx, setLitSet, timers) {
  const delayOn  = 200 + Math.random() * 1200; // wait before turning on
  const stayOn   = 600 + Math.random() * 1400; // how long it stays on
  const delayOff = 300 + Math.random() * 1000; // gap before next cycle

  const tOn = setTimeout(() => {
    setLitSet(prev => new Set([...prev, idx]));

    const tOff = setTimeout(() => {
      setLitSet(prev => { const n = new Set(prev); n.delete(idx); return n; });

      // schedule next cycle
      const tNext = setTimeout(() => scheduleWindow(idx, setLitSet, timers), delayOff);
      timers.current.push(tNext);
    }, stayOn);
    timers.current.push(tOff);
  }, delayOn);
  timers.current.push(tOn);
}

export default function HotelChip({ label }) {
  const [active, setActive] = useState(false);
  const [litSet, setLitSet] = useState(new Set());
  const timers              = useRef([]);

  const handleEnter = () => {
    setActive(true);
    setLitSet(new Set());
    // kick off every window on its own random schedule
    for (let i = 0; i < TOTAL; i++) {
      scheduleWindow(i, setLitSet, timers);
    }
  };

  const handleLeave = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setActive(false);
    setLitSet(new Set());
  };

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  return (
    <Box
      className="hotel-chip-wrapper"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      {/* ── Resting pill ── */}
      <Box className={`hotel-pill ${active ? "hotel-pill--hidden" : ""}`}>
        <span className="hotel-pill-icon"><HotelIcon fontSize="small" /></span>
        <span className="hotel-pill-label">{label}</span>
      </Box>

      {/* ── Hotel building ── */}
      <Box className={`hotel-building ${active ? "hotel-building--visible" : ""}`}>
        <svg width="72" height="88" viewBox="0 0 72 88" className="hotel-svg">
          <rect x="0" y="80" width="72" height="8" rx="2" className="hotel-ground" />
          <rect x="8" y="10" width="56" height="70" rx="3" className="hotel-body" />
          <rect x="8" y="4" width="56" height="10" rx="2" className="hotel-roof" />
          <text x="36" y="13" textAnchor="middle" className="hotel-sign">H</text>
          <rect x="29" y="62" width="14" height="18" rx="2" className="hotel-door" />

          {Array.from({ length: ROWS }).map((_, row) =>
            Array.from({ length: COLS }).map((_, col) => {
              const idx = row * COLS + col;
              const wx  = 12 + col * 10;
              const wy  = 16 + row * 8;
              if (row >= 5 && col >= 1 && col <= 3) return null;
              return (
                <rect
                  key={idx}
                  x={wx} y={wy}
                  width="6" height="5"
                  rx="1"
                  className={`hotel-window ${litSet.has(idx) ? "hotel-window--lit" : ""}`}
                />
              );
            })
          )}
        </svg>
      </Box>
    </Box>
  );
}
