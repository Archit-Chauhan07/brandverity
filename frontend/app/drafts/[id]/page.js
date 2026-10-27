"use client";

import { useCallback, useEffect, useState } from "react";
import { api, getUser } from "../../../lib/api";

const STATUSES = ["draft", "pending_manager", "pending_reviewer", "approved"];

export default function DraftPage({ params }) {
  const id = params.id;
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [user, setUser] = useState(null);
  const [comment, setComment] = useState("");
  const [workflowComment, setWorkflowComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [needsHumanReview, setNeedsHumanReview] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await api.getDraft(id);
      // Real backend shape is FLAT (id, title, ..., findings, approvals,
      // comments, history) — not the {draft, ...} wrapper in the brief.
      // Tolerate both.
      const draft = res.draft || res;
      const findings = res.findings || [];
      setData({
        draft,
        findings,
        approvals: res.approvals || [],
        comments: res.comments || [],
        history: res.history || [],
        note: res.note,
      });
      if (typeof res.needs_human_review === "boolean") {
        setNeedsHumanReview(res.needs_human_review);
      } else if (typeof draft.needs_human_review === "boolean") {
        setNeedsHumanReview(draft.needs_human_review);
      } else {
        // Review outcome stashed by the upload page (GET /drafts/{id} does
        // not carry needs_human_review).
        try {
          const stashed = window.sessionStorage.getItem(`brandverity_review_${id}`);
          if (stashed) setNeedsHumanReview(JSON.parse(stashed).needs_human_review);
        } catch { /* ignore */ }
      }
      // History endpoint is separate in the contract; merge it in if the
      // detail payload did not already include history. Real shape:
      // {draft_id, status, approvals, audit: [...]}.
      if (!res.history) {
        try {
          const h = await api.getHistory(id);
          const audit = Array.isArray(h) ? h : h.audit || h.history || [];
          const appr = Array.isArray(h) ? [] : h.approvals || [];
          setData((prev) =>
            prev
              ? { ...prev, history: audit, approvals: appr.length ? appr : prev.approvals }
              : prev
          );
        } catch {
          // History is nice-to-have; the detail payload is enough.
        }
      }
    } catch (err) {
      setError(err.message);
    }
  }, [id]);

  useEffect(() => {
    setUser(getUser());
    load();
  }, [load]);

  async function run(fn, successMsg) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const res = await fn();
      if (res && typeof res.needs_human_review === "boolean") {
        setNeedsHumanReview(res.needs_human_review);
      }
      if (successMsg) setNotice(successMsg);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !data) return <><h1>Draft</h1><p className="error">{error}</p></>;
  if (!data) return <><h1>Draft</h1><p className="muted">Loading…</p></>;

  const { draft, findings, approvals, comments, history } = data;
  const status = draft.status;
  const role = user?.role || "";
  const roleLower = role.toLowerCase();

  const canSubmit = roleLower === "creator" && status === "draft";
  const canManagerAct = roleLower === "manager" && status === "pending_manager";
  const canReviewerAct = roleLower === "reviewer" && status === "pending_reviewer";
  const canPublish = roleLower === "admin" && status === "approved";
  const showHumanReviewBanner =
    needsHumanReview === true && findings.length === 0;

  return (
    <>
      <h1>{draft.title}</h1>
      <p>
        <span className="badge">{status}</span>{" "}
        <span className="muted">
          {draft.content_type ? `· ${draft.content_type}` : ""}
          {draft.tenant_id ? ` · tenant ${draft.tenant_id}` : ""}
        </span>
      </p>
      {error && <p className="error">{error}</p>}
      {notice && <p className="banner">{notice}</p>}

      {showHumanReviewBanner && (
        <p className="banner">
          ⚠️ Needs human review — the automated review found no hard rule
          violations, but flagged this draft for a person to check before it
          moves on.
        </p>
      )}

      <section className="card">
        <h2>Draft body</h2>
        <p style={{ whiteSpace: "pre-wrap" }}>{draft.body}</p>
        {draft.meta && Object.keys(draft.meta).length > 0 && (
          <p className="muted">
            Meta: {JSON.stringify(draft.meta)}
          </p>
        )}
        <button
          className="secondary"
          disabled={busy}
          onClick={() =>
            run(() => api.reviewDraft(id), "Review re-run.")
          }
        >
          Re-run review
        </button>
      </section>

      <section className="card">
        <h2>Findings ({findings.length})</h2>
        {findings.length === 0 && (
          <p className="muted">No findings yet. Run a review to check this draft.</p>
        )}
        {findings.map((f) => (
          <article key={f.id} className="card">
            <p>
              <strong>
                {f.rule_code}
                {f.rule_version ? ` v${f.rule_version}` : ""}
              </strong>{" "}
              <span className="badge">{f.status || "open"}</span>
            </p>
            {f.quoted_span && <blockquote>{f.quoted_span}</blockquote>}
            {f.why && <p>{f.why}</p>}
            {f.suggested_edit && (
              <p>
                <strong>Suggested minimal edit:</strong> {f.suggested_edit}
              </p>
            )}
            <button
              disabled={busy}
              onClick={() =>
                run(
                  () => api.decideFinding(id, f.id, "accept"),
                  "Finding accepted."
                )
              }
            >
              Accept
            </button>
            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                run(
                  () => api.decideFinding(id, f.id, "reject"),
                  "Finding rejected."
                )
              }
            >
              Reject
            </button>
          </article>
        ))}
      </section>

      <section className="card">
        <h2>Workflow</h2>
        {!canSubmit && !canManagerAct && !canReviewerAct && !canPublish && (
          <p className="muted">
            No workflow action is available for your role ({role || "not logged in"})
            at status <code>{status}</code>. Workflow: draft → pending_manager →
            pending_reviewer → approved → published.
          </p>
        )}
        {canSubmit && (
          <button
            disabled={busy}
            onClick={() => run(() => api.submitDraft(id), "Submitted to Manager.")}
          >
            Submit to Manager
          </button>
        )}
        {(canManagerAct || canReviewerAct) && (
          <>
            <label htmlFor="workflow-comment">Comment (required for reject)</label>
            <textarea
              id="workflow-comment"
              value={workflowComment}
              onChange={(e) => setWorkflowComment(e.target.value)}
              placeholder="Add a comment for approve / reject…"
              style={{ minHeight: 80 }}
            />
            <button
              disabled={busy}
              onClick={() =>
                run(
                  () => api.approveDraft(id, workflowComment),
                  "Approved."
                )
              }
            >
              Approve
            </button>
            <button
              className="danger"
              disabled={busy}
              onClick={() =>
                run(() => api.rejectDraft(id, workflowComment), "Rejected back to draft.")
              }
            >
              Reject
            </button>
          </>
        )}
        {canPublish && (
          <button
            disabled={busy}
            onClick={() => run(() => api.publishDraft(id), "Published.")}
          >
            Publish
          </button>
        )}
        <p className="muted">
          Hiding these buttons by role/status is display only — the server
          enforces every transition.
        </p>
      </section>

      <section className="card">
        <h2>Comments ({comments.length})</h2>
        {comments.length === 0 && <p className="muted">No comments yet.</p>}
        {comments.map((c, i) => (
          <p key={c.id || i}>
            <strong>
              {c.author || c.username || (c.author_id ? `User ${c.author_id}` : "—")}:
            </strong>{" "}
            {c.text || c.body || c.comment}
            {c.created_at && <span className="muted"> · {c.created_at}</span>}
          </p>
        ))}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!comment.trim()) return;
            run(() => api.addComment(id, comment), "Comment added.").then(() =>
              setComment("")
            );
          }}
        >
          <label htmlFor="new-comment">Add a comment</label>
          <textarea
            id="new-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            style={{ minHeight: 80 }}
          />
          <button type="submit" disabled={busy || !comment.trim()}>
            Add comment
          </button>
        </form>
      </section>

      <section className="card">
        <h2>History &amp; approvals</h2>
        {approvals.length > 0 && (
          <>
            <h3>Approvals</h3>
            {approvals.map((a, i) => (
              <p key={a.id || i} className="muted">
                {a.from_status && a.to_status
                  ? `${a.from_status} → ${a.to_status} (user ${a.actor_id})`
                  : JSON.stringify(a)}
                {a.comment ? ` — ${a.comment}` : ""}
              </p>
            ))}
          </>
        )}
        {history.length === 0 && approvals.length === 0 && (
          <p className="muted">No history yet.</p>
        )}
        {history.map((h, i) => (
          <p key={h.id || i} className="muted">
            {h.action || h.event || h.status || JSON.stringify(h)}
            {h.detail ? ` — ${h.detail}` : ""}
            {h.comment ? ` — ${h.comment}` : ""}
            {h.created_at ? ` · ${h.created_at}` : ""}
          </p>
        ))}
        <p className="muted">Statuses: {STATUSES.join(" → ")} (reject returns to draft).</p>
      </section>
    </>
  );
}
