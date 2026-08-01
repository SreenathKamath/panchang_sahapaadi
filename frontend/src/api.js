// In local dev, relative paths ("/api/...") go through Vite's dev proxy (see
// vite.config.js) straight to the backend on :8000. In production (e.g. Vercel), the
// frontend and backend are on different domains -- VITE_API_BASE_URL (set at build
// time, see frontend/.env.production.example) points requests at the real backend
// instead. Falls back to "" (relative) when unset, so local dev needs no config.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export function apiUrl(path) {
  return `${API_BASE}${path}`;
}

async function request(path, options) {
  const res = await fetch(apiUrl(path), options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request to ${path} failed (${res.status})`);
  }
  return res.json();
}

export function sendChatQuery(query) {
  return request("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export function fetchMonths() {
  return request("/api/months");
}

export function fetchMonthDays(monthName) {
  return request(`/api/months/${encodeURIComponent(monthName)}/days`);
}
