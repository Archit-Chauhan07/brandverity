"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

const STATUSES = ["draft", "pending_manager", "pending_reviewer", "approved"];

export default function QueuePage() {
  const [drafts, setDrafts] = useState([]);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listDrafts()
      .then((res) => setDrafts(Array.isArray(res) ? res : res.drafts || []))
      .catch((err) => setError(err.message));
  }, []);

  const shown = filter === "all" ? drafts : drafts.filter((d) => d.status === filter);
  const grouped = STATUSES.map((s) => ({
    status: s,
    items: drafts.filter((d) => d.status === s),
  }));

  return (
    <>
      <h1>Approval queue</h1>
      <p className="muted">
        Drafts grouped by workflow status. Click a draft to review its findings
        and act on it.
      </p>
      {error && <p className="error">{error}</p>}
      <p>
        <label htmlFor="filter">Filter by status: </label>
        <select
          id="filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ width: "auto" }}
        >
          <option value="all">All ({drafts.length})</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s} ({drafts.filter((d) => d.status === s).length})
            </option>
          ))}
        </select>
      </p>

      {filter === "all" ? (
        grouped.map(({ status, items }) => (
          <section key={status} className="card">
            <h2>
              {status} ({items.length})
            </h2>
            {items.length === 0 && <p className="muted">None.</p>}
            {items.map((d) => (
              <p key={d.id}>
                <Link href={`/drafts/${d.id}`}>{d.title || `Draft ${d.id}`}</Link>{" "}
                <span className="muted">· {d.content_type || ""}</span>
              </p>
            ))}
          </section>
        ))
      ) : (
        <section className="card">
          <h2>
            {filter} ({shown.length})
          </h2>
          {shown.length === 0 && <p className="muted">None.</p>}
          {shown.map((d) => (
            <p key={d.id}>
              <Link href={`/drafts/${d.id}`}>{d.title || `Draft ${d.id}`}</Link>
            </p>
          ))}
        </section>
      )}
    </>
  );
}
