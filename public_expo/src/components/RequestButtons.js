import { useApp } from "../AppContext";
import { submitButtonClickRequest } from "../requests";

// Four generic demo buttons that just send a `button_click` request with no
// server-side handler today - harmless connectivity-test buttons, kept for
// parity with the prototype.
export default function RequestButtons() {
  const { sessionName, userId, userLocation, setStatusText } = useApp();

  function send(label) {
    submitButtonClickRequest(sessionName, userId, userLocation, `request ${label}`)
      .then(() => setStatusText(`request ${label} sent`))
      .catch((error) => setStatusText(error.message));
  }

  return (
    <div className="request-actions" aria-label="Client requests">
      {["X", "Y", "A", "B"].map((label) => (
        <button
          key={label}
          className="request-action-button"
          type="button"
          aria-label={`Send request ${label}`}
          onClick={() => send(label)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
