export default function StatusCard({ status }) {
  return (
    <section className="status-card" aria-live="polite">
      <p className="status-label">Location</p>
      <p id="location-status">{status}</p>
    </section>
  );
}
