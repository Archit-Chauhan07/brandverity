"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "../../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = await api.forgotPassword(email);
      setDone(data.message || "Sent.");
    } catch (err) {
      setDone(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Forgot password</h1>
      <p className="muted">
        Enter the email you signed up with. If it is registered, a reset
        link is on its way.
      </p>
      {done ? (
        <div className="card">
          <p>{done}</p>
          <p className="muted">
            <Link href="/login">Back to login</Link>
          </p>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="card">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <button type="submit" disabled={busy}>
            {busy ? "Sending…" : "Send reset link"}
          </button>
        </form>
      )}
    </>
  );
}
