// Small fetch wrapper for the BrandVerity backend.
// Base URL comes from NEXT_PUBLIC_API_URL, default http://localhost:8000.
// Auth: Authorization: Bearer <token>; token + user are stored in
// localStorage after login (keys below).

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const TOKEN_KEY = "brandverity_token";
export const USER_KEY = "brandverity_user";

export function getToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(token, user) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const msg =
      (data && (data.detail || data.message || data.error)) ||
      `Request failed (${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export const api = {
  login: (username, password) =>
    apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  listTenants: () => apiFetch("/tenants"),
  listRules: (tenantId) => apiFetch(`/tenants/${tenantId}/rules`),
  createTenant: (name) =>
    apiFetch("/tenants", { method: "POST", body: JSON.stringify({ name }) }),
  listCustomRules: (tenantId) =>
    apiFetch(`/tenants/${tenantId}/custom-rules`),
  createCustomRule: (tenantId, payload) =>
    apiFetch(`/tenants/${tenantId}/custom-rules`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createDraft: (payload) =>
    apiFetch("/drafts", { method: "POST", body: JSON.stringify(payload) }),
  listDrafts: (status) =>
    apiFetch(status ? `/drafts?status=${encodeURIComponent(status)}` : "/drafts"),
  getDraft: (id) => apiFetch(`/drafts/${id}`),
  reviewDraft: (id) =>
    apiFetch(`/drafts/${id}/review`, { method: "POST", body: JSON.stringify({}) }),
  decideFinding: (draftId, findingId, decision) =>
    apiFetch(`/drafts/${draftId}/findings/${findingId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  submitDraft: (id) =>
    apiFetch(`/drafts/${id}/submit`, { method: "POST", body: JSON.stringify({}) }),
  approveDraft: (id, comment) =>
    apiFetch(`/drafts/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ comment: comment || "" }),
    }),
  rejectDraft: (id, comment) =>
    apiFetch(`/drafts/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ comment: comment || "" }),
    }),
  addComment: (id, text) =>
    apiFetch(`/drafts/${id}/comments`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  getHistory: (id) => apiFetch(`/drafts/${id}/history`),
  getInsights: (tenantId) =>
    apiFetch(tenantId ? `/insights?tenant_id=${encodeURIComponent(tenantId)}` : "/insights"),
  publishDraft: (id) =>
    apiFetch(`/drafts/${id}/publish`, { method: "POST", body: JSON.stringify({}) }),
};
