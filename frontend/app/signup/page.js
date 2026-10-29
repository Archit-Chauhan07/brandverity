"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "../../lib/api";

export default function SignupPage() {
  const [username, setUsername] = useState("");
  const [brand, setBrand] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setDone("");
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const data = await api.register({
        username,
        email,
        password,
        brand_name: brand,
      });
      setDone(data.message || "Account created. Check your email.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Sign up</h1>
      <p className="muted">
        Create your own brand workspace. You will be its Admin, and you can
        add your own brand rules from the Brands page.
      </p>
      {error && <p className="error">{error}</p>}
      {done ? (
        <div className="card">
          <p>{done}</p>
          <p className="muted">
            Click the link in the email to activate your account, then{" "}
            <Link href="/login">log in</Link>.
          </p>
        </div>
      ) : (
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
          <label htmlFor="brand">Brand name</label>
          <input
            id="brand"
            type="text"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            required
            placeholder="e.g. Harbor Roasters"
          />
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <label htmlFor="password">Password (at least 8 characters)</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
          />
          <label htmlFor="confirm">Confirm password</label>
          <input
            id="confirm"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            autoComplete="new-password"
          />
          <button type="submit" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>
      )}
      <p className="muted">
        Already have an account? <Link href="/login">Log in</Link>. Just want
        to try the demo? Use a demo login on the{" "}
        <Link href="/login">login page</Link> (password <code>demo123</code>).
      </p>
    </>
  );
}
