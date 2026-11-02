"use client";

// Round 3 audit export page: per-brand, tenant-scoped. Shows who did
// what, when, under which rule version, and what decision was made —
// plus the honest record of email-notification attempts (sent only
// when mail actually went out). Rows written before Round 3 have no
// timestamp; the page says so instead of inventing one.

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, getUser } from "../../lib/api";

function download(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function toCsv(rows) {
  const esc = (v) =>
    `"${String(v ?? "").replaceAll('"', '""')}"`;
  const header = [
    "id",
    "actor",
    "action",
    "entity",
    "entity_id",
    "detail",
    "created_at",
    "decision",
    "rule_code",
    "rule_version",
  ];
  const lines = [header.join(",")];
  for (const r of rows) {
    lines.push(
      header.map((h) => esc(r[h])).join(",")
    );
  }
  return lines.join("\n");
}

export default function AuditPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const user = getUser();
    if (!user) {
      setError("Log in to view this brand's audit export.");
      return;
    }
    api
      .getAuditExport(user.tenant_id)
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <>
        <h1>Audit export</h1>
        <p className="error">{error}</p>
        <p>
          <Link href="/login">Log in</Link>
        </p>
      </>
    );
  }
  if (!data) return <p className="muted">Loading audit export…</p>;

  const rows = data.rows || [];
  const notes = data.notifications || [];

  return (
    <>
      <h1>Audit export</h1>
      <p className="muted">
        Brand: {data.tenant_name || data.tenant_id} · Exported{" "}
        {data.exported_at || ""}
      </p>
      <p className="muted">{data.note}</p>
      <p>
        <button
          onClick={() =>
            download(
              "audit-export.json",
              JSON.stringify(data, null, 2),
              "application/json"
            )
          }
        >
          Download JSON
        </button>{" "}
        <button onClick={() => download("audit-export.csv", toCsv(rows), "text/csv")}>
          Download CSV
        </button>
      </p>

      <section className="card">
        <h2>
          Audit rows ({rows.length}
          {data.rows_without_timestamp
            ? `, ${data.rows_without_timestamp} without a timestamp`
            : ""}
          )
        </h2>
        {rows.length === 0 && <p className="muted">No audit rows yet.</p>}
        {rows.map((r) => (
          <p key={r.id}>
            <strong>{r.actor || `user ${r.actor_id}`}</strong> · {r.action} ·{" "}
            {r.entity} {r.entity_id} ·{" "}
            {r.created_at || "time unknown (before Round 3)"}
            {r.decision ? ` · decision: ${r.decision}` : ""}
            {r.rule_code
              ? ` · rule: ${r.rule_code} (${r.rule_version})`
              : ""}
            {r.detail ? ` · ${r.detail}` : ""}
          </p>
        ))}
      </section>

      <section className="card">
        <h2>Notification attempts ({notes.length})</h2>
        <p className="muted">
          Email-first notifications. A notification is shown as sent only
          when the email actually went out; otherwise it is unsent, with
          the reason shown.
        </p>
        {notes.length === 0 && (
          <p className="muted">No notification attempts yet.</p>
        )}
        {notes.map((n) => (
          <p key={n.id}>
            Draft {n.draft_id} → {n.recipient || n.recipient_role} (
            {n.recipient_role}) · {n.kind} · <strong>{n.status}</strong>
            {n.reason ? ` · ${n.reason}` : ""} · {n.created_at || ""}
          </p>
        ))}
      </section>
    </>
  );
}
