"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export default function VerifyPage() {
  const [status, setStatus] = useState("checking");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [resent, setResent] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setStatus("no-token");
      return;
    }
    api
      .verifyEmail(token)
      .then((data) => {
        setStatus("ok");
        setMessage(data.message || "Email verified.");
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err.message);
      });
  }, []);

  async function onResend(e) {
    e.preventDefault();
    setResent("");
    try {
      const data = await api.resendVerification(email);
      setResent(data.message || "Sent.");
    } catch (err) {
      setResent(err.message);
    }
  }

  return (
    <>
      <h1>Email verification</h1>
      {status === "checking" && <p className="muted">Verifying your link…</p>}
      {status === "ok" && (
        <div className="card">
          <p>{message}</p>
          <p>
            <Link href="/login">Log in now</Link>
          </p>
        </div>
      )}
      {status === "no-token" && (
        <p className="muted">
          No verification link was opened. Signed up already? Check your
          inbox for the link, or request a new one below.
        </p>
      )}
      {status === "error" && (
        <div className="card">
          <p className="error">{message}</p>
          <p className="muted">
            Links expire after 24 hours. Request a new one:
          </p>
        </div>
      )}
      {(status === "error" || status === "no-token") && (
        <form onSubmit={onResend} className="card">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <button type="submit">Send a new verification link</button>
          {resent && <p className="muted">{resent}</p>}
        </form>
      )}
    </>
  );
}
