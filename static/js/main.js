// App shell: routing, sign-in gate, live updates | Owner: Priyesh Patel, owned by no feature
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.


import { api, connectLive } from "./api.js";
import * as auth from "./auth.js";
import * as dashboard from "./dashboard.js";
import * as settingsView from "./settings.js";
import { $, $$, setBanner, startTicker } from "./ui.js";

// Feature screens load only if their file exists, so features can be merged in any order.
const noop = () => {};
const stub = new Proxy({}, { get: (_, key) => (key === "then" ? undefined : noop) });   // not a "thenable", or await would hang
const load = async name => { try { return await import(`./${name}.js`); } catch { console.warn(`${name}.js not merged yet`); return stub; } };
const features = await Promise.all(["queue", "tickets", "guides", "report", "coverage"].map(load));
const [queue, tickets, guides, report, coverage] = features;

// Each feature lists the user stories it has built: `export const stories = ["US-01", ...]`.
// Anything in index.html marked data-story="US-xx" is removed until one of its stories is merged,
// so the page never shows a button or screen whose code isn't there yet.
const built = new Set(features.flatMap(f => (Array.isArray(f.stories) ? f.stories : [])));
$$("[data-story]").forEach(el => { if (!el.dataset.story.split(" ").some(s => built.has(s))) el.remove(); });
const exists = name => !!document.getElementById("v-" + name);

const PUBLIC = ["kiosk", "lobby", "desk-status"];                 // no sign-in needed
const STAFF = ["dashboard", "counter", "tickets", "handover", "guides", "coverage", "timeaway", "report", "notifications", "settings"];
let view = "dashboard";

function route() {
  const hash = location.hash.slice(1);
  const isPublic = PUBLIC.includes(hash) && exists(hash);
  let show;
  if (isPublic) show = hash;
  else if (!auth.isSignedIn()) show = "login";
  else show = view = STAFF.includes(hash) && exists(hash) ? hash : view;

  document.body.classList.toggle("kiosk", isPublic);
  document.body.classList.remove("nav-open");
  $("#kioskExit").hidden = !isPublic || !auth.isSignedIn();
  const shell = !isPublic && show !== "login";
  $("#side").hidden = !shell;
  $("#topbar").hidden = !shell;
  document.querySelector(".app").style.gridTemplateColumns = shell ? "" : "minmax(0, 1fr)";
  $$("main > section").forEach(s => { s.hidden = s.id !== "v-" + show; });
  $$(".nav [data-tab]").forEach(b => (b.dataset.tab === show ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current")));
  if (show === "login") $("#loginUser").focus();
  refreshView(show);
}

function refreshView(show) {
  ({ kiosk: queue.refreshKiosk, lobby: queue.refreshLobby, counter: queue.refreshCounter,
     tickets: tickets.refreshDrafts, handover: tickets.refreshHandover, guides: guides.refresh,
     report: report.refresh, coverage: coverage.refreshBoard, timeaway: coverage.refreshTimeAway, notifications: coverage.refreshFeed,
     "desk-status": coverage.refreshPublic, dashboard: dashboard.refresh, settings: settingsView.refresh }[show] || (() => {}))();
}

function currentView() { return $$("main > section").find(s => !s.hidden)?.id.slice(2); }

/** The server said `topic` changed: refresh only the screens that show it. */
function onLive(topic) {
  const v = currentView();
  if (topic === "*") { refreshView(v); if (auth.isSignedIn()) { coverage.refreshMine(); badges(); } return; }
  const wants = { queue: ["kiosk", "lobby", "counter", "dashboard"], tickets: ["tickets", "dashboard"], handover: ["handover", "dashboard"],
                  guides: ["guides"], status: ["coverage", "desk-status", "dashboard"], notifications: ["notifications"], timeaway: ["timeaway"] }[topic] || [];
  if (wants.includes(v)) refreshView(v);
  if (auth.isSignedIn()) badges();
}

/** Small counts on the tabs so staff notice things on other screens.
 *  Each count is fetched on its own, so one feature that isn't merged yet can't stop the others. */
async function badges() {
  const set = (id, n) => { const b = $(id); if (b) { b.textContent = n; b.hidden = !n; } };
  const count = async (id, url, pick) => {
    if (!$(id)) return;                     // that tab isn't on the page yet
    try { set(id, pick(await api(url))); } catch { /* not merged yet, or signed out mid-way */ }
  };
  count("#qBadge", "/api/queue", q => q.waiting.length);
  count("#tBadge", "/api/drafts?raised=false&mine=true", d => d.length);
  count("#hBadge", "/api/handover", h => h.notes.length);
  if (auth.isSenior()) {
    count("#nBadge", "/api/notifications", f => { if ($("#bellDot")) $("#bellDot").hidden = !f.unread; return f.unread; });
    if ($("#taBadge")) set("#taBadge", await coverage.timeAwayBadge());
  }
}

async function boot() {
  $$(".nav [data-tab]").forEach(b => b.addEventListener("click", () => { location.hash = "#" + b.dataset.tab; }));
  $("#signOutNav").addEventListener("click", auth.signOut);
  $("#menuBtn").addEventListener("click", () => document.body.classList.toggle("nav-open"));
  document.addEventListener("click", e => { if (document.body.classList.contains("nav-open") && !e.target.closest(".side, #menuBtn")) document.body.classList.remove("nav-open"); });
  $("#topSearch")?.addEventListener("submit", e => { e.preventDefault(); guides.search($("#topSearchQ").value); location.hash = "#guides"; });
  document.addEventListener("keydown", e => {
    if (e.key === "/" && $("#topSearchQ") && !e.target.closest("input, textarea, select") && !$("#topbar").hidden) { e.preventDefault(); $("#topSearchQ").focus(); }
  });
  window.addEventListener("hashchange", route);
  window.addEventListener("counterpoint:signed-out", () => { auth.forget(); location.hash = ""; route(); });

  const settings = await api("/api/settings");
  auth.init({ signedIn: () => { location.hash = "#" + view; route(); coverage.refreshMine(); badges(); } });
  queue.init(settings);
  tickets.init(settings);
  guides.init(settings);
  report.init();
  coverage.init();
  settingsView.init();

  await auth.restore();
  auth.render();
  route();
  if (auth.isSignedIn()) { coverage.refreshMine(); badges(); }

  startTicker();
  setInterval(() => refreshView(currentView()), 60000);   // times like "unattended since" and missed calls
  connectLive(onLive, ok => setBanner(ok ? "" : "Reconnecting to the server… the screen will update when it's back."));
}

boot();
