import { useApp } from "../AppContext";

export default function StatusCard() {
  const { statusText } = useApp();
  return (
    <section className="status-card" aria-live="polite">
      <p className="status-label">Location</p>
      <p id="location-status">{statusText}</p>
    </section>
  );
}
