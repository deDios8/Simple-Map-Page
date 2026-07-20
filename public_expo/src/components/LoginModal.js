import { useState } from "react";
import { useApp } from "../AppContext";
import { DEFAULT_SESSION_NAME } from "../firebase";

export default function LoginModal() {
  const { login } = useApp();
  const [sessionName, setSessionNameInput] = useState(DEFAULT_SESSION_NAME);
  const [userId, setUserIdInput] = useState("");
  const [password, setPasswordInput] = useState("");
  const [status, setStatus] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    setStatus("");
    const result = login(sessionName, userId, password);
    if (!result.ok && result.error) {
      setStatus(result.error);
    }
  }

  return (
    <div className="id-modal-overlay">
      <div className="id-modal-card">
        <p className="eyebrow">Welcome</p>
        <h2>Enter your Session and ID</h2>
        <form onSubmit={handleSubmit}>
          <label className="modal-field-row">
            <span className="modal-field-label">Session Name</span>
            <input
              type="text"
              placeholder="Session name"
              value={sessionName}
              onChange={(event) => setSessionNameInput(event.target.value)}
              autoComplete="off"
              required
            />
          </label>
          <label className="modal-field-row">
            <span className="modal-field-label">User ID</span>
            <input
              type="text"
              placeholder="Your identifier"
              value={userId}
              onChange={(event) => setUserIdInput(event.target.value)}
              autoComplete="off"
              required
            />
          </label>
          <label className="modal-field-row">
            <span className="modal-field-label">Password</span>
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(event) => setPasswordInput(event.target.value)}
              autoComplete="off"
              required
            />
          </label>
          <p aria-live="polite">{status}</p>
          <button className="primary-button" type="submit">Start tracking</button>
        </form>
      </div>
    </div>
  );
}
