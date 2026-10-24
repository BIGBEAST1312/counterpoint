// Feature 5 · Desk coverage + supervisor notifications | Owner: Aarya Patel
// AI disclosure: with guidance of Claude (Anthropic).
import { api, ApiError } from "./api.js";
import { isSignedIn, setMyStatus } from "./auth.js";
import { $, esc, fmtClock, fmtDate, fmtDur, isoDay, ms, personHTML, toast } from "./ui.js";

// Product v1 (Deliverable 2): E9 · Keep the desk covered, plus US-33 supervisor notifications.
// E10 (US-30 to US-32, the public "Is the IT desk covered?" page) comes in Product v2; E11 (time away) in the final product.
export const stories = ["US-26", "US-27", "US-28", "US-29", "US-33"];

const STATUSES = [
  { key: "on_desk", label: "On desk", hint: "Covering the desk" },
  { key: "on_break", label: "On break", hint: "Short break" },
  { key: "at_lunch", label: "At lunch", hint: "Lunch break" },
  { key: "stepped_away", label: "Stepped away", hint: "Helping elsewhere" },
  { key: "off_shift", label: "Off shift", hint: "Done for the day" },
];
const AWAY = ["on_break", "at_lunch", "stepped_away"];
let mine = null;

export function init() {
  $("#myStatus").addEventListener("click", e => {
    const b = e.target.closest("button[data-s]");
    if (b) change(b.dataset.s, false);
  });
  $("#statusMsg").addEventListener("click", e => {
    const b = e.target.closest("button[data-confirm]");
    if (b?.dataset.confirm === "yes") change(b.dataset.s, true);
    if (b?.dataset.confirm === "no") $("#statusMsg").innerHTML = "";   // "Stay on desk"
  });
  $("#nDay").value = isoDay();
  $("#nDay").max = isoDay();
  $("#nDay").addEventListener("change", refreshFeed);
  $("#nRead").addEventListener("click", async () => { await api("/api/notifications/read", { method: "POST" }); refreshFeed(); });
}

/** US-26 set my status, US-28 confirm before leaving the desk empty. */
async function change(status, confirmEmpty) {
  const back = AWAY.includes(status) ? $("#backAt").value || null : null;
  try {
    mine = await api("/api/status/me", { method: "PATCH", body: { status, back_at: back, confirm_empty: confirmEmpty } });
    $("#statusMsg").innerHTML = "";
    $("#backAt").value = "";
    toast(`You're now: ${mine.label}`);
    drawMine(); refreshBoard();
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      $("#statusMsg").innerHTML = `<div class="callout warn dialog"><span>${esc(err.message)}</span>
        <div class="acts"><button class="btn" data-confirm="no">Stay on desk</button>
        <button class="btn primary" data-confirm="yes" data-s="${esc(status)}">Leave it unattended</button></div></div>`;
    } else toast(err.message);
  }
}

function drawMine() {
  setMyStatus(mine);
  $("#myStatus").innerHTML = STATUSES.map(s => `<button type="button" data-s="${s.key}" aria-pressed="${mine && mine.status === s.key}">
    <span class="pill ${s.key}">${s.label}</span><small>${s.hint}</small></button>`).join("");
}

export async function refreshMine() {
  try { mine = await api("/api/status/me"); drawMine(); } catch { /* signed out */ }
}

/** US-27 who's on and who's away, US-29 plan breaks. */
export async function refreshBoard() {
  if (!isSignedIn()) return;
  let b;
  try { [b] = await Promise.all([api("/api/status/board"), refreshMine()]); } catch { return; }
  const person = (p) => personHTML({ id: p.staff_id, display_name: p.name });
  $("#onDesk").innerHTML = b.on_desk.length ? b.on_desk.map(p => `<div class="prow"><span class="who">${person(p)}</span>
      <span class="t">on since ${fmtClock(p.since)} · ${fmtDur(Date.now() - ms(p.since))}</span></div>`).join("")
    : `<div class="callout bad">Nobody is on desk. The public page shows the desk as unattended.</div>`;
  $("#away").innerHTML = b.away.length ? b.away.map(p => `<div class="prow"><span class="who">${person(p)}</span>
      <span class="pill ${p.status}">${esc(p.label)}</span><span class="t">since ${fmtClock(p.since)}</span>
      ${p.back_at ? `<span class="${p.overdue ? "late" : "t"}">${p.overdue ? "overdue: " : ""}back at ${fmtClock(p.back_at)}</span>` : ""}</div>`).join("")
    : `<p class="hint">Nobody is away.</p>`;
  $("#breakTip").innerHTML = b.break_suggestion ? `<div class="callout good">☕ ${esc(b.break_suggestion.message)}</div>`
    : b.alone ? `<div class="callout warn">Only one person is on desk, so no break is suggested right now.</div>` : "";
}

/** US-33: the staff feed of check-ins, check-outs, breaks and returns, with times.
 *  Everyone sees it; only the supervisor and shift leads have an unread list to clear. */
export async function refreshFeed() {
  if (!isSignedIn()) return;
  let f;
  try { f = await api(`/api/notifications?day=${$("#nDay").value || isoDay()}`); } catch (err) { $("#nFeed").innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
  $("#nRead").hidden = !f.can_mark_read;
  $("#nEmail").textContent = !f.can_mark_read ? "Every check-in, break and check-out on the team, with its time."
    : f.email_enabled ? "Each notification is also emailed to the supervisor."
    : "In-app only. Set up email in .env (see the README) to also email the supervisor.";
  const KIND = { checked_in: "Checked in", checked_out: "Checked out", on_break: "On break", at_lunch: "At lunch", stepped_away: "Stepped away", back: "Back on desk" };
  const PILL = { checked_in: "on_desk", back: "on_desk", checked_out: "off_shift", on_break: "on_break", at_lunch: "at_lunch", stepped_away: "stepped_away" };
  $("#nFeed").innerHTML = f.items.length ? `<div class="feed">${f.items.map(i => `<div class="fitem${i.read || !f.can_mark_read ? "" : " unread"}">
      <span class="time">${esc(i.time)}</span><span>${esc(i.message)}</span>
      <span class="pill k ${PILL[i.kind] || ""}">${KIND[i.kind] || esc(i.kind)}${i.emailed ? " · emailed" : ""}</span></div>`).join("")}</div>`
    : `<div class="empty"><strong>No staff activity on ${fmtDate(f.day + "T12:00:00")}</strong>Check-ins, breaks and check-outs show up here as they happen.</div>`;
}
