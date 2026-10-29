"use client";

import Link from "next/link";
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
      <p className="muted">
        Use your username or email. Demo tenant: Northpeak Coffee — use a
        demo account below, or <Link href="/signup">create your own account</Link>.
      </p>
      {error && <p className="error">{error}</p>}
      {error.includes("verify your email") && (
        <p className="muted">
          <Link href="/verify">Request a new verification link</Link>
        </p>
      )}
      <form onSubmit={onSubmit} className="card">
        <label htmlFor="username">Username or email</label>
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
      <p className="muted">
        New here? <Link href="/signup">Sign up</Link> ·{" "}
        <Link href="/forgot-password">Forgot password?</Link>
      </p>
    </>
  );
}
