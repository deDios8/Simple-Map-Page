import { useEffect, useRef } from "react";
import { useApp } from "../AppContext";
import { submitDismissMessageRequest } from "../requests";

export default function MessageModal() {
  const { pendingMessage, dismissMessage, sessionName, userId, userLocation } = useApp();
  const dialogRef = useRef(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (pendingMessage) {
      if (!dialog.open) dialog.showModal();
    } else if (dialog.open) {
      dialog.close();
    }
  }, [pendingMessage]);

  function handleOk() {
    if (!pendingMessage) return;
    // Optimistically mark it dismissed so the modal won't re-flash before the
    // ~2s server echo removes it from the zone's messages array.
    dismissMessage(pendingMessage);
    submitDismissMessageRequest(sessionName, userId, pendingMessage, userLocation).catch((error) => {
      console.error(error);
    });
  }

  return (
    <dialog ref={dialogRef} aria-labelledby="message-modal-heading" aria-describedby="message-modal-text">
      <article className="message-modal-card">
        <p className="eyebrow">Message</p>
        <p id="message-modal-text">{pendingMessage}</p>
        <div className="message-modal-actions">
          <button className="primary-button" type="button" onClick={handleOk}>
            OK
          </button>
        </div>
      </article>
    </dialog>
  );
}
