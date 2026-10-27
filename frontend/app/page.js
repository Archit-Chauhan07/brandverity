import Link from "next/link";

export default function Home() {
  return (
    <>
      <h1>BrandVerity</h1>
      <p>
        Brand governance for <strong>Northpeak Coffee</strong> (fictional demo
        tenant). Creators draft content, an automated review flags it against
        the brand rulebook, and a Manager then a Reviewer approve it — step by
        step. Nothing auto-publishes.
      </p>
      <div className="card">
        <h2>How it works</h2>
        <ol>
          <li>
            <strong>Creator</strong> writes a draft and submits it (draft →{" "}
            <code>pending_manager</code>).
          </li>
          <li>
            <strong>Manager</strong> approves it (→{" "}
            <code>pending_reviewer</code>) or rejects it back to draft with a
            comment.
          </li>
          <li>
            <strong>Reviewer</strong> approves it (→ <code>approved</code>) or
            rejects it back to draft with a comment.
          </li>
          <li>
            <strong>Admin</strong> publishes an approved draft.
          </li>
        </ol>
        <p className="muted">
          Buttons are hidden when they do not apply to your role and the draft
          status — but hiding is never the enforcement; the server enforces
          every transition.
        </p>
      </div>
      <p>
        <Link className="btn" href="/upload">Create a draft</Link>
        <Link className="btn secondary" href="/queue">Approval queue</Link>
        <Link className="btn secondary" href="/insights">Insights</Link>
      </p>
      <p className="muted">
        Demo logins (password <code>demo123</code>): admin / Admin, creator /
        Creator, manager / Manager, reviewer / Reviewer.
      </p>
    </>
  );
}
