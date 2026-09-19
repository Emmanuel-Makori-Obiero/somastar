/**
 * Thin API client. Every screen goes through this service layer rather
 * than calling fetch() directly, per CLAUDE.md section 2.1.
 */
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "somastar_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

// Backend errors come as {detail:{error:{message}}} (HTTPException) or {error:{message}} (handlers).
function extractMessage(data) {
  if (!data) return null;
  if (typeof data.detail === "string") return data.detail;
  return data.detail?.error?.message || data.error?.message || null;
}

async function request(path, { method = "GET", body, isForm = false, auth = true } = {}) {
  const headers = {};
  if (!isForm && body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Can't reach the server. Check your connection and try again.");
  }

  if (!res.ok) {
    let message = "Something went wrong.";
    try {
      message = extractMessage(await res.json()) || message;
    } catch {
      // non-JSON error body: keep default message
    }
    // An expired/invalid token on a protected call: sign the user out everywhere.
    if (res.status === 401 && auth) {
      setToken(null);
      window.dispatchEvent(new Event("somastar:unauthorized"));
    }
    const error = new Error(message);
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null;
  return res.json();
}

export const authApi = {
  register: (payload) => request("/api/auth/register", { method: "POST", body: payload, auth: false }),
  login: (payload) => request("/api/auth/login", { method: "POST", body: payload, auth: false }),
  me: () => request("/api/auth/me"),
};

export const examApi = {
  list: ({ limit = 50, offset = 0 } = {}) => request(`/api/exams?limit=${limit}&offset=${offset}`),
  get: (id) => request(`/api/exams/${id}`),
  upload: (formData) => request("/api/exams", { method: "POST", body: formData, isForm: true }),
  reanalyze: (id) => request(`/api/exams/${id}/reanalyze`, { method: "POST" }),
  remove: (id) => request(`/api/exams/${id}`, { method: "DELETE" }),
};

export const assessmentApi = {
  get: () => request("/api/assessment"),
  chat: (message) => request("/api/assessment/chat", { method: "POST", body: { message } }),
};

export const revisionApi = {
  list: (status) => request(`/api/revision${status ? `?status=${status}` : ""}`),
  setStatus: (id, status) => request(`/api/revision/${id}`, { method: "PATCH", body: { status } }),
};

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated() {
  return !!getToken();
}
