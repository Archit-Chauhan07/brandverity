"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getUser } from "../../lib/api";

export default function UploadPage() {
  const router = useRouter();
  const [tenants, setTenants] = useState([]);
  const [tenantId, setTenantId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [contentType, setContentType] = useState("text");
  const [primaryColor, setPrimaryColor] = useState("#1F4D3A");
  const [logoDistorted, setLogoDistorted] = useState(false);
  const [altText, setAltText] = useState("");
  const [textColor, setTextColor] = useState("");
  const [bgColor, setBgColor] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    setUser(getUser());
    api
      .listTenants()
      .then((list) => {
        const arr = Array.isArray(list) ? list : list.tenants || [];
        setTenants(arr);
        if (arr.length > 0) {
          const northpeak =
            arr.find((t) => /northpeak/i.test(t.name || "")) || arr[0];
          setTenantId(String(northpeak.id));
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const meta =
        contentType === "image"
          ? {
              primary_color: primaryColor,
              logo_distorted: logoDistorted,
              alt_text: altText,
              text_color: textColor,
              bg_color: bgColor,
            }
          : {};
      const draft = await api.createDraft({
        tenant_id: tenantId,
        title,
        body,
        content_type: contentType,
        meta,
      });
      const id = draft.id ?? draft.draft?.id;
      if (!id) throw new Error("Backend did not return a draft id.");
      // Run the automated review, then go to the draft page.
      // A review failure should not lose the draft: still navigate.
      try {
        const review = await api.reviewDraft(id);
        // GET /drafts/{id} does not carry needs_human_review, so stash the
        // review outcome for the draft page to pick up.
        if (review && typeof review.needs_human_review === "boolean") {
          window.sessionStorage.setItem(
            `brandverity_review_${id}`,
            JSON.stringify({ needs_human_review: review.needs_human_review })
          );
        }
      } catch (reviewErr) {
        setError(`Draft created, but review failed: ${reviewErr.message}`);
      }
      router.push(`/drafts/${id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Create a draft</h1>
      {!user && (
        <p className="error">
          You are not logged in. Log in first — otherwise the backend will
          reject the create request.
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <form onSubmit={onSubmit} className="card">
        <label htmlFor="tenant">Tenant</label>
        <select
          id="tenant"
          value={tenantId}
          onChange={(e) => setTenantId(e.target.value)}
          required
        >
          <option value="" disabled>
            Select a tenant…
          </option>
          {tenants.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>

        <label htmlFor="title">Title</label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />

        <label htmlFor="content-type">Content type</label>
        <select
          id="content-type"
          value={contentType}
          onChange={(e) => setContentType(e.target.value)}
        >
          <option value="text">Text</option>
          <option value="image">Image</option>
        </select>

        <label htmlFor="body">Body</label>
        <textarea
          id="body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={
            contentType === "image"
              ? "Caption / copy that goes with the image…"
              : "Write the draft copy here…"
          }
          required
        />

        {contentType === "image" && (
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend style={{ fontWeight: 700, marginTop: "0.75rem" }}>
              Image details
            </legend>
            <div className="row">
              <div>
                <label htmlFor="primary-color">Primary color</label>
                <input
                  id="primary-color"
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                />
                <span className="muted"> {primaryColor}</span>
              </div>
              <div>
                <label htmlFor="text-color">Text color</label>
                <input
                  id="text-color"
                  type="text"
                  placeholder="#FFFFFF"
                  value={textColor}
                  onChange={(e) => setTextColor(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="bg-color">Background color</label>
                <input
                  id="bg-color"
                  type="text"
                  placeholder="#1F4D3A"
                  value={bgColor}
                  onChange={(e) => setBgColor(e.target.value)}
                />
              </div>
            </div>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={logoDistorted}
                onChange={(e) => setLogoDistorted(e.target.checked)}
              />
              Logo is distorted / stretched
            </label>
            <label htmlFor="alt-text">Alt text</label>
            <input
              id="alt-text"
              type="text"
              value={altText}
              onChange={(e) => setAltText(e.target.value)}
              placeholder="Describe the image for accessibility…"
            />
          </fieldset>
        )}

        <button type="submit" disabled={busy || !tenantId}>
          {busy ? "Creating…" : "Create draft & run review"}
        </button>
      </form>
    </>
  );
}
