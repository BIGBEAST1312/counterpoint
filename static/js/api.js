// Shared API client | Owner: Priyesh Patel, owned by no feature
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
//
// Every part talks to the backend through api(). It adds the sign-in token, turns error
// responses into readable messages, and signs the user out if the server says the token expired.

const TOKEN_KEY = "counterpoint.token";

export const session = {
  get token() { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set(token) { try { localStorage.setItem(TOKEN_KEY, token); } catch { /* private mode */ } },
  clear() { try { localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ } },
};

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

/** FastAPI puts errors in `detail`: a string for our own errors, a list for validation errors. */
function readDetail(body, fallback) {
  const d = body && body.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return String(d[0].msg || fallback).replace(/^Value error, /, "");
  return fallback;
}

export async function api(path, { method = "GET", body, raw = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = session.token;
  if (token) headers.Authorization = "Bearer " + token;

  let res;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check the connection and try again.");
  }
  if (res.status === 401 && token) {
    session.clear();
    window.dispatchEvent(new Event("counterpoint:signed-out"));
  }
  if (!res.ok) {
    let parsed = null;
    try { parsed = await res.json(); } catch { /* not JSON */ }
    throw new ApiError(res.status, readDetail(parsed, res.statusText || "Request failed"));
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

/** Open the live-update socket. onTopic("queue" | "tickets" | "handover" | "guides" | "status" | "notifications" | "*")
 *  is called on every change;
 *  "*" means "we just (re)connected, refresh everything". Reconnects with backoff if the server restarts. */
export function connectLive(onTopic, onStatus = () => {}) {
  let delay = 1000;
  const open = () => {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ws.onopen = () => { delay = 1000; onStatus(true); onTopic("*"); };
    ws.onmessage = e => { try { onTopic(JSON.parse(e.data).topic); } catch { /* ignore junk */ } };
    ws.onclose = () => { onStatus(false); setTimeout(open, delay); delay = Math.min(delay * 2, 15000); };
  };
  open();
}
