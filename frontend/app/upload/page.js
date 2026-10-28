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
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState("");
  const [imageInfo, setImageInfo] = useState(null);
  const [colorMeasured, setColorMeasured] = useState(false);
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

  // One-click judge samples (?sample=flagged|clean|ambiguous): prefill the
  // form so a sample draft is one submit away from its review.
  useEffect(() => {
    const samples = {
      flagged: {
        title: "Autumn blend launch",
        body: "The best coffee in the world. Our single-origin blend from three regions. Since 2015.",
        contentType: "text",
      },
      clean: {
        title: "Small-batch roast note",
        body: "Hand-roasted in small batches since 2019. Our 250 g bags are roasted in small batches.",
        contentType: "text",
      },
      ambiguous: {
        title: "Tasting note",
        body: "A bold roast with a rich, smooth taste.",
        contentType: "text",
      },
    };
    const sample =
      samples[new URLSearchParams(window.location.search).get("sample")];
    if (sample) {
      setTitle(sample.title);
      setBody(sample.body);
      setContentType(sample.contentType);
    }
  }, []);

  function hexFromRgb(r, g, b) {
    const h = (v) => v.toString(16).padStart(2, "0");
    return `#${h(r)}${h(g)}${h(b)}`.toUpperCase();
  }

  // Measure the dominant color of the uploaded image file itself, in the
  // browser, and use it as the primary color the checker tests. The user
  // can still override it with the color picker afterwards.
  function onImageFileChange(e) {
    const file = e.target.files && e.target.files[0];
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(file || null);
    setImageInfo(null);
    setColorMeasured(false);
    if (!file) {
      setImagePreview("");
      return;
    }
    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file (PNG, JPG, WebP, …).");
      setImagePreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setImagePreview(url);
    const img = new Image();
    img.onload = () => {
      const maxSide = 200;
      const scale = Math.min(
        1,
        maxSide / Math.max(img.naturalWidth, img.naturalHeight)
      );
      const w = Math.max(1, Math.round(img.naturalWidth * scale));
      const h = Math.max(1, Math.round(img.naturalHeight * scale));
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(img, 0, 0, w, h);
      let data;
      try {
        data = ctx.getImageData(0, 0, w, h).data;
      } catch {
        setError(
          "Could not read this image's pixels; set the primary color manually."
        );
        return;
      }
      const buckets = new Map();
      for (let i = 0; i < data.length; i += 4) {
        const a = data[i + 3];
        if (a < 128) continue;
        const key = `${data[i] >> 4},${data[i + 1] >> 4},${data[i + 2] >> 4}`;
        buckets.set(key, (buckets.get(key) || 0) + 1);
      }
      let bestKey = null;
      let bestCount = 0;
      for (const [key, count] of buckets) {
        if (count > bestCount) {
          bestCount = count;
          bestKey = key;
        }
      }
      if (bestKey) {
        const [r, g, b] = bestKey
          .split(",")
          .map((v) => parseInt(v, 10) * 16 + 8);
        const hex = hexFromRgb(r, g, b);
        setPrimaryColor(hex);
        setColorMeasured(true);
        setImageInfo({
          width: img.naturalWidth,
          height: img.naturalHeight,
          name: file.name,
          size: file.size,
          dominant: hex,
        });
      }
    };
    img.onerror = () => {
      setError(
        "Could not open that image file; set the primary color manually."
      );
    };
    img.src = url;
  }

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
              ...(imageInfo
                ? {
                    image_width: imageInfo.width,
                    image_height: imageInfo.height,
                    image_filename: imageInfo.name,
                  }
                : {}),
              color_source: colorMeasured
                ? "measured from uploaded file"
                : "entered manually",
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
            <label htmlFor="image-file">
              Image file (optional — we measure its real colors)
            </label>
            <input
              id="image-file"
              type="file"
              accept="image/*"
              onChange={onImageFileChange}
            />
            {imagePreview && (
              <div>
                <img
                  src={imagePreview}
                  alt="Uploaded preview"
                  style={{
                    maxWidth: "220px",
                    marginTop: "0.5rem",
                    border: "1px solid #ddd",
                  }}
                />
                {imageInfo && (
                  <p className="muted">
                    {imageInfo.name} · {imageInfo.width}×{imageInfo.height}px
                    · measured dominant color {imageInfo.dominant}
                  </p>
                )}
              </div>
            )}
            <div className="row">
              <div>
                <label htmlFor="primary-color">Primary color</label>
                <input
                  id="primary-color"
                  type="color"
                  value={primaryColor}
                  onChange={(e) => {
                    setPrimaryColor(e.target.value);
                    setColorMeasured(false);
                  }}
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
