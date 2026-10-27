"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, saveSession } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await api.login(username, password);
      saveSession(data.token, data.user);
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Log in</h1>
      <p className="muted">Demo tenant: Northpeak Coffee. Use a demo account below.</p>
      {error && <p className="error">{error}</p>}
      <form onSubmit={onSubmit} className="card">
        <label htmlFor="username">Username</label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          autoComplete="username"
        />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
        />
        <button type="submit" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p className="muted">
        Demo logins (password <code>demo123</code>): <code>admin</code> (Admin),{" "}
        <code>creator</code> (Creator), <code>manager</code> (Manager),{" "}
        <code>reviewer</code> (Reviewer).
      </p>
    </>
  );
}
