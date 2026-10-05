import { useId, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import HelpTip from './HelpTip';
import './InterestsPie.css';

const COLORS = [
  '#38644b',
  '#2d667b',
  '#8b4562',
  '#90651e',
  '#565e86',
  '#a44832',
  '#526a32',
  '#6c5186',
  '#326e69',
  '#9a493f',
  '#725b37',
  '#405f86',
  '#80526a',
  '#606936',
];
const title = (key) => key.replaceAll('_', ' ');
const point = (percent, radius = 110) => {
  const angle = (percent / 100) * Math.PI * 2 - Math.PI / 2;
  return [140 + radius * Math.cos(angle), 140 + radius * Math.sin(angle)];
};
const wedge = (start, size) => {
  if (size >= 99.999999) return 'M140 30 A110 110 0 1 1 140 250 A110 110 0 1 1 140 30 Z';
  const [x1, y1] = point(start);
  const [x2, y2] = point(start + size);
  return `M140 140 L${x1} ${y1} A110 110 0 ${size > 50 ? 1 : 0} 1 ${x2} ${y2} Z`;
};
const angleAt = (event, rect) =>
  Math.atan2(
    event.clientY - rect.top - rect.height / 2,
    event.clientX - rect.left - rect.width / 2
  );

/** Percentages are a view of the parent's weights, never a second source of truth. */
export default function InterestsPie({ attributes, weights, onChange, disabled }) {
  const hintId = useId();
  const chart = useRef(null);
  const gesture = useRef(null);
  const suppressClick = useRef(false);
  const [dragging, setDragging] = useState(null);
  const [over, setOver] = useState(false);
  const [resizing, setResizing] = useState(null);
  const [message, setMessage] = useState('');
  const [emptyDraft, setEmptyDraft] = useState(null);
  const total = attributes.reduce((sum, key) => sum + (Number(weights[key]) || 0), 0);
  // Existing presets may contain relative weights. Display their equivalent shares.
  const divisor = Math.max(1, total);
  const shares = Object.fromEntries(
    attributes.map((key) => [key, ((Number(weights[key]) || 0) / divisor) * 100])
  );
  const allocated = Math.min(
    100,
    Object.values(shares).reduce((sum, share) => sum + share, 0)
  );
  const available = Math.max(0, 100 - allocated);
  let start = 0;
  const slices = attributes
    .filter((key) => shares[key] > 0)
    .map((key) => {
      const slice = {
        key,
        start,
        size: shares[key],
        color: COLORS[attributes.indexOf(key) % COLORS.length],
      };
      start += slice.size;
      return slice;
    });
  const writeShare = (key, value, base = shares) => {
    if (disabled || !Number.isFinite(value)) return;
    setEmptyDraft(null);
    const others = attributes.reduce((sum, item) => sum + (item === key ? 0 : base[item]), 0);
    const next = Math.max(0, Math.min(Math.round(value * 10) / 10, 100 - others));
    onChange(
      Object.fromEntries(attributes.map((item) => [item, (item === key ? next : base[item]) / 100]))
    );
  };
  const add = (key) => {
    if (disabled || shares[key] > 0) return;
    if (available < 0.05) {
      setMessage('Circle full. Shrink or remove a slice to make room.');
      return;
    }
    const size = Math.min(10, available);
    writeShare(key, size);
    setMessage(`${title(key)} added. Drag its edge to change its share.`);
  };
  const inside = (event) => {
    const rect = chart.current.getBoundingClientRect();
    const x = (event.clientX - rect.left - rect.width / 2) / rect.width;
    const y = (event.clientY - rect.top - rect.height / 2) / rect.height;
    return x * x + y * y <= (110 / 280) ** 2;
  };
  const beginResize = (event, slice) => {
    if (disabled || event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    gesture.current = {
      key: slice.key,
      base: shares,
      value: slice.size,
      angle: angleAt(event, chart.current.getBoundingClientRect()),
    };
    setResizing(slice.key);
    setMessage('');
  };
  const moveResize = (event) => {
    const drag = gesture.current;
    if (!drag || disabled) return;
    const angle = angleAt(event, chart.current.getBoundingClientRect());
    // Unwrap across 12 o'clock; dragging through the seam must not jump 100%.
    let delta = angle - drag.angle;
    if (delta > Math.PI) delta -= Math.PI * 2;
    if (delta < -Math.PI) delta += Math.PI * 2;
    drag.angle = angle;
    const otherTotal = attributes.reduce(
      (sum, key) => sum + (key === drag.key ? 0 : drag.base[key]),
      0
    );
    drag.value = Math.max(
      0.1,
      Math.min(100 - otherTotal, drag.value + (delta * 100) / (Math.PI * 2))
    );
    writeShare(drag.key, drag.value, drag.base);
  };
  const endResize = () => {
    gesture.current = null;
    setResizing(null);
  };
  const stopDrop = () => {
    setDragging(null);
    setOver(false);
    gesture.current = null;
  };
  const moveTopic = (event) => {
    if (!gesture.current?.topic || disabled) return;
    setOver(inside(event));
    gesture.current.moved ||=
      Math.hypot(event.clientX - gesture.current.x, event.clientY - gesture.current.y) > 6;
  };
  const finishTopic = (event) => {
    if (!gesture.current?.topic) return;
    suppressClick.current = gesture.current.moved;
    if (gesture.current.moved && inside(event)) add(gesture.current.topic);
    stopDrop();
  };
  return (
    <div className="interest-editor">
      <p className="lab-note" id={hintId}>
        Drop a topic into the circle. Drag its edge to resize.
        <HelpTip label="trip weights">
          Shares cannot exceed 100% altogether. Shrink a slice to free space; other topics stay
          unchanged. Click a topic to add it, or use the percentage fields. Slice handles also work
          with arrow keys. At run time, the server scales the chosen shares to sum to 100%; unused
          space is not an interest.
        </HelpTip>
      </p>
      <div
        className={`interest-chart ${dragging && !disabled ? 'is-dropping' : ''} ${over ? 'is-over' : ''}`}
        ref={chart}
      >
        <svg
          viewBox="0 0 280 280"
          role="img"
          aria-label={`Trip interests: ${allocated.toFixed(1)}% allocated, ${available.toFixed(1)}% free`}
        >
          <circle cx="140" cy="140" r="110" className="interest-empty-circle" />
          {slices.map((slice) => (
            <g key={slice.key}>
              <path
                d={wedge(slice.start, slice.size)}
                fill={slice.color}
                stroke="var(--lab-paper)"
                strokeWidth="2"
              >
                <title>
                  {title(slice.key)}: {slice.size.toFixed(1)}%
                </title>
              </path>
              {slice.size >= 6 && (
                <text
                  x={point(slice.start + slice.size / 2, 72)[0]}
                  y={point(slice.start + slice.size / 2, 72)[1]}
                  className="interest-slice-label"
                >
                  {Math.round(slice.size)}%
                </text>
              )}
            </g>
          ))}
          {!slices.length && (
            <text x="140" y="140" className="interest-empty-label">
              Your trip, your mix
            </text>
          )}
        </svg>
        {slices.map((slice) => {
          const [x, y] = point(slice.start + slice.size, 113);
          const max = Math.max(0, 100 - (allocated - slice.size));
          return (
            <button
              key={slice.key}
              type="button"
              role="slider"
              className={`interest-edge ${resizing === slice.key ? 'is-resizing' : ''}`}
              style={{
                left: `${x / 2.8}%`,
                top: `${y / 2.8}%`,
                '--slice-color': slice.color,
                '--edge-angle': `${(slice.start + slice.size) * 3.6}deg`,
              }}
              aria-label={`Resize ${title(slice.key)}`}
              aria-valuemin={0}
              aria-valuemax={Number(max.toFixed(1))}
              aria-valuenow={Number(slice.size.toFixed(1))}
              aria-valuetext={`${slice.size.toFixed(1)} percent`}
              aria-describedby={hintId}
              disabled={disabled}
              title={`Drag to resize ${title(slice.key)}`}
              onPointerDown={(event) => beginResize(event, slice)}
              onPointerMove={moveResize}
              onPointerUp={endResize}
              onPointerCancel={endResize}
              onLostPointerCapture={endResize}
              onKeyDown={(event) => {
                const delta = event.shiftKey ? 5 : 1;
                const values = {
                  ArrowRight: slice.size + delta,
                  ArrowUp: slice.size + delta,
                  ArrowLeft: slice.size - delta,
                  ArrowDown: slice.size - delta,
                  Home: 0,
                  End: max,
                };
                if (event.key in values) {
                  event.preventDefault();
                  writeShare(slice.key, values[event.key]);
                }
              }}
            >
              <span className="interest-edge-grip" aria-hidden="true" />
            </button>
          );
        })}
        {dragging && !disabled && (
          <div className="interest-drop-overlay" aria-hidden="true">
            <strong>{available < 0.05 ? 'Circle full' : `Drop ${title(dragging)} here`}</strong>
            <span>
              {available < 0.05
                ? 'Shrink a slice to make room'
                : `${available.toFixed(0)}% available`}
            </span>
          </div>
        )}
      </div>
      <div className="interest-total">
        <strong>{allocated.toFixed(1).replace('.0', '')}% allocated</strong>
        <span>
          {available < 0.05
            ? '100% limit reached'
            : `${available.toFixed(1).replace('.0', '')}% free`}
        </span>
      </div>
      <div className="interest-selected">
        {slices.map((slice) => (
          <div className="interest-row" key={slice.key}>
            <span
              className="interest-swatch"
              style={{ background: slice.color }}
              aria-hidden="true"
            />
            <label htmlFor={`${hintId}-${slice.key}`}>{title(slice.key)}</label>
            <div className="interest-percent">
              <input
                id={`${hintId}-${slice.key}`}
                aria-label={`Interest ${title(slice.key)} percentage`}
                type="number"
                min="0"
                max={Math.ceil(Math.max(0, 100 - (allocated - slice.size)) * 10) / 10}
                step="any"
                value={
                  emptyDraft?.key === slice.key ? emptyDraft.text : Number(slice.size.toFixed(1))
                }
                disabled={disabled}
                onChange={(event) => {
                  const text = event.target.value;
                  // Keep the control mounted while clearing or typing a decimal.
                  if (text === '' || Number(text) === 0) setEmptyDraft({ key: slice.key, text });
                  else writeShare(slice.key, Number(text));
                }}
                onBlur={() => {
                  if (emptyDraft?.key === slice.key) writeShare(slice.key, 0);
                }}
              />
              <span>%</span>
            </div>
            <button
              type="button"
              className="interest-remove"
              aria-label={`Remove ${title(slice.key)}`}
              disabled={disabled}
              onClick={() => writeShare(slice.key, 0)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <p className="interest-topics-label">
        Add a topic <span>Drag or click</span>
      </p>
      <div className="interest-topics">
        {attributes
          .filter((key) => shares[key] <= 0)
          .map((key) => (
            <button
              type="button"
              key={key}
              disabled={disabled}
              className="interest-topic"
              aria-label={`Add ${title(key)}`}
              style={{ '--slice-color': COLORS[attributes.indexOf(key) % COLORS.length] }}
              onClick={(event) => {
                if (suppressClick.current && event.detail !== 0) {
                  suppressClick.current = false;
                  return;
                }
                add(key);
              }}
              onPointerDown={(event) => {
                if (disabled || event.button !== 0) return;
                event.preventDefault();
                suppressClick.current = false;
                setMessage('');
                event.currentTarget.setPointerCapture(event.pointerId);
                gesture.current = { topic: key, x: event.clientX, y: event.clientY, moved: false };
                setDragging(key);
              }}
              onPointerMove={moveTopic}
              onPointerUp={finishTopic}
              onPointerCancel={stopDrop}
              onLostPointerCapture={stopDrop}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  suppressClick.current = true;
                  stopDrop();
                }
              }}
            >
              <span className="interest-topic-dot" aria-hidden="true" />
              {title(key)}
              <span aria-hidden="true">+</span>
            </button>
          ))}
        {slices.length === attributes.length && (
          <span className="lab-note">All topics are in your mix.</span>
        )}
      </div>
      <p className="interest-feedback" role="status">
        {message ||
          (available >= 0.05 && allocated > 0
            ? 'At run time, chosen shares scale to 100%.'
            : !allocated
              ? 'Add at least one topic to run.'
              : 'Shrink an edge or remove a topic to free space.')}
      </p>
    </div>
  );
}
InterestsPie.propTypes = {
  attributes: PropTypes.arrayOf(PropTypes.string).isRequired,
  weights: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool.isRequired,
};
