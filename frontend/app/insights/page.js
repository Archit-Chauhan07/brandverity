"use client";

import { useEffect, useState } from "react";
import { api, getUser } from "../../lib/api";

function Bars({ data }) {
  const entries = Object.entries(data || {});
  if (entries.length === 0) return <p className="muted">No data yet.</p>;
  const max = Math.max(...entries.map(([, v]) => Number(v) || 0), 1);
  return (
    <div>
      {entries.map(([key, value]) => (
        <div key={key}>
          <span>
            {key}: <strong>{value}</strong>
          </span>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${((Number(value) || 0) / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function InsightsPage() {
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const user = getUser();
    api
      .getInsights(user?.tenant_id)
      .then(setInsights)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <>
      <h1>Insights</h1>
      <p className="banner">
        Day 1 placeholder dashboard — real counts from{" "}
        <code>GET /insights</code>, rendered as plain lists and bars. No
        charts library yet.
      </p>
      {error && <p className="error">{error}</p>}
      {!insights && !error && <p className="muted">Loading…</p>}
      {insights && (
        <>
          <section className="card">
            <h2>Findings per rule</h2>
            {/* Real backend key is findings_per_rule; the brief said
                findings_by_rule — accept either. */}
            <Bars data={insights.findings_per_rule ?? insights.findings_by_rule} />
          </section>
          <section className="card">
            <h2>Drafts per status</h2>
            <Bars data={insights.drafts_per_status ?? insights.drafts_by_status} />
          </section>
        </>
      )}
    </>
  );
}
