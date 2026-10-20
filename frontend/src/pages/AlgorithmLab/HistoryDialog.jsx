import PropTypes from 'prop-types';
import { useLayoutEffect, useRef } from 'react';

export default function HistoryDialog({ onClose, children }) {
  const dialog = useRef(null);
  useLayoutEffect(() => {
    const element = dialog.current;
    const opener = document.activeElement;
    element.showModal();
    return () => {
      element.close();
      if (opener?.isConnected) opener.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      id="lab-history-panel"
      className="lab-history-dialog"
      aria-label="Studio history"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="lab-preset-heading">
        <h2>History</h2>
        <button type="button" onClick={onClose}>
          Close history
        </button>
      </div>
      {children}
    </dialog>
  );
}
HistoryDialog.propTypes = {
  onClose: PropTypes.func.isRequired,
  children: PropTypes.node.isRequired,
};
