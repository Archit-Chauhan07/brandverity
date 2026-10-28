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
        Real counts and patterns from <code>GET /insights</code>, computed
        from your drafts&apos; actual findings — no charts library, just the
        numbers.
      </p>
      {error && <p className="error">{error}</p>}
      {!insights && !error && <p className="muted">Loading…</p>}
      {insights && (
        <>
          <section className="card">
            <h2>Most repeated mistake</h2>
            {insights.most_repeated_mistake ? (
              <p>
                <strong>{insights.most_repeated_mistake.rule_code}</strong> —{" "}
                {insights.most_repeated_mistake.count} findings.{" "}
                {insights.most_repeated_mistake.rule_text}
              </p>
            ) : (
              <p className="muted">No findings yet.</p>
            )}
          </section>
          <section className="card">
            <h2>Least clear rule</h2>
            {insights.least_clear_rule ? (
              <p>
                <strong>{insights.least_clear_rule.rule_code}</strong> —{" "}
                {insights.least_clear_rule.rejected} of{" "}
                {insights.least_clear_rule.total} findings rejected (
                {Math.round(insights.least_clear_rule.rejection_rate * 100)}
                %). {insights.least_clear_rule.rule_text}
                <br />
                <em>
                  Suggested rewrite:{" "}
                  {insights.least_clear_rule.suggested_rewrite}
                </em>
              </p>
            ) : (
              <p className="muted">
                Not enough data yet — needs a rule with at least 2 findings.
              </p>
            )}
          </section>
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
