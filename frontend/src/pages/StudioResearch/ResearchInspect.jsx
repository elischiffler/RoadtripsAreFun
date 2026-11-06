import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import PropTypes from 'prop-types';

const Inspection = createContext(null);
const Group = createContext(null);

export function InspectionProvider({ children }) {
  const tooltipId = useId();
  const [active, setActive] = useState(null);
  const [position, setPosition] = useState(null);
  const timer = useRef();
  const bubble = useRef(null);
  const cancel = useCallback(() => clearTimeout(timer.current), []);
  const hide = useCallback((immediate = false) => {
    clearTimeout(timer.current);
    if (immediate) setActive(null);
    else timer.current = setTimeout(() => setActive(null), 100);
  }, []);
  const show = useCallback((target, instant = false) => {
    clearTimeout(timer.current);
    const reveal = () => {
      if (!target.anchor.isConnected) return;
      setPosition(null);
      setActive(target);
    };
    if (instant) reveal();
    else timer.current = setTimeout(reveal, 140);
  }, []);

  useLayoutEffect(() => {
    if (!active) return;
    const anchor = active.anchor.getBoundingClientRect();
    const bounds = bubble.current?.getBoundingClientRect();
    if (!bounds) return;
    const left = Math.max(
      12,
      Math.min(
        window.innerWidth - bounds.width - 12,
        anchor.left + anchor.width / 2 - bounds.width / 2
      )
    );
    const above = anchor.top >= bounds.height + 20;
    const top = Math.max(
      12,
      Math.min(
        window.innerHeight - bounds.height - 12,
        above ? anchor.top - bounds.height - 10 : anchor.bottom + 10
      )
    );
    setPosition({ left, top });
  }, [active]);

  useEffect(() => {
    if (!active) return;
    const dismiss = (event) => {
      if (!active.anchor.contains(event.target) && !bubble.current?.contains(event.target))
        hide(true);
    };
    const escape = (event) => {
      if (event.key === 'Escape') hide(true);
    };
    const reposition = (event) => {
      if (!(event.target instanceof Node) || !bubble.current?.contains(event.target)) hide(true);
    };
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('keydown', escape);
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    return () => {
      document.removeEventListener('pointerdown', dismiss);
      document.removeEventListener('keydown', escape);
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
    };
  }, [active, hide]);
  useEffect(() => cancel, [cancel]);
  useLayoutEffect(() => {
    if (active && !active.anchor.isConnected) hide(true);
  }, [active, children, hide]);
  const value = useMemo(
    () => ({ show, hide, activeId: active?.id, tooltipId }),
    [show, hide, active, tooltipId]
  );
  return (
    <Inspection.Provider value={value}>
      {children}
      {active &&
        createPortal(
          <div
            ref={bubble}
            id={tooltipId}
            role="tooltip"
            className="research-inspect-tooltip"
            style={{ ...position, visibility: position ? 'visible' : 'hidden' }}
            onPointerEnter={cancel}
            onPointerLeave={() => hide()}
          >
            <strong>{active.insight.value}</strong>
            {active.insight.detail && (
              <span className="research-inspect-detail">{active.insight.detail}</span>
            )}
          </div>,
          document.body
        )}
    </Inspection.Provider>
  );
}
InspectionProvider.propTypes = { children: PropTypes.node.isRequired };

export function InspectionGroup({ as: Tag = 'svg', children, ...props }) {
  const [selected, setSelected] = useState(null);
  const root = useRef(null);
  useLayoutEffect(() => {
    if (selected && !root.current?.querySelector('[data-inspection-target][tabindex="0"]'))
      setSelected(null);
  }, [selected, children]);
  const value = useMemo(() => ({ selected, setSelected }), [selected]);
  return (
    <Group.Provider value={value}>
      <Tag {...props} ref={root} data-inspection-chart="">
        {children}
      </Tag>
    </Group.Provider>
  );
}
InspectionGroup.propTypes = { as: PropTypes.string, children: PropTypes.node.isRequired };

export function InspectMark({
  as: Tag = 'g',
  insight,
  label,
  first = false,
  disabled = false,
  children,
  ...props
}) {
  const context = useContext(Inspection);
  const group = useContext(Group);
  const id = useId();
  if (!context || disabled) return <Tag {...props}>{children}</Tag>;
  const reveal = (event, instant) =>
    context.show({ id, anchor: event.currentTarget, insight }, instant);
  const navigate = (event) => {
    if (['Enter', ' '].includes(event.key)) {
      event.preventDefault();
      reveal(event, true);
      return;
    }
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key))
      return;
    const marks = [
      ...(event.currentTarget
        .closest('[data-inspection-chart]')
        ?.querySelectorAll('[data-inspection-target]') ?? []),
    ];
    if (!marks.length) return;
    event.preventDefault();
    const index = marks.indexOf(event.currentTarget);
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? marks.length - 1
          : (index + (['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1) + marks.length) %
            marks.length;
    marks[next].focus();
  };
  return (
    <Tag
      {...props}
      role={Tag === 'td' ? undefined : 'button'}
      aria-label={label}
      aria-describedby={context.activeId === id ? context.tooltipId : undefined}
      data-inspection-target=""
      tabIndex={group?.selected ? (group.selected === id ? 0 : -1) : first ? 0 : -1}
      onPointerEnter={(event) => {
        if (event.pointerType !== 'touch') reveal(event, false);
      }}
      onPointerLeave={(event) => {
        if (document.activeElement !== event.currentTarget) context.hide();
      }}
      onFocus={(event) => {
        group?.setSelected(id);
        reveal(event, true);
      }}
      onBlur={() => context.hide()}
      onClick={(event) => {
        event.currentTarget.focus();
        reveal(event, true);
      }}
      onKeyDown={navigate}
    >
      {children}
    </Tag>
  );
}
InspectMark.propTypes = {
  as: PropTypes.string,
  insight: PropTypes.shape({
    value: PropTypes.string.isRequired,
    detail: PropTypes.string,
  }),
  label: PropTypes.string,
  first: PropTypes.bool,
  disabled: PropTypes.bool,
  children: PropTypes.node.isRequired,
};
