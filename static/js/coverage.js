// Feature 5 · Desk coverage + supervisor notifications | Owner: Aarya Patel
// AI disclosure: with guidance of Claude (Anthropic).
import { api, ApiError } from "./api.js";
import { isSignedIn, setMyStatus } from "./auth.js";
import { $, esc, fmtClock, fmtDate, fmtDur, isoDay, ms, personHTML, seg, showErr, toast } from "./ui.js";

// Stories built in this file (E9 + E10 + E11). main.js shows the parts of the page marked with these.
export const stories = ["US-26", "US-27", "US-28", "US-29", "US-30", "US-31", "US-32", "US-33", "US-34", "US-35", "US-36", "US-37"];

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
  initTimeAway();
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

/** US-30 to US-32: what library staff see. No names, no sign-in. */
export async function refreshPublic() {
  let c;
  try { c = await api("/api/coverage"); } catch { return; }
  const title = { open: "Open", unattended: "Unattended", closed: "Closed" }[c.state];
  $("#publicCov").innerHTML = `
    <div class="brandrow"><img src="/img/logo-mark.svg" alt="">IT Support desk, Murray Library</div>
    <div class="state ${c.state}"><div class="lbl">Right now</div><h2>${title}</h2><p>${esc(c.message)}</p>
      ${c.back_message ? `<p><b>${esc(c.back_message)}</b></p>` : ""}</div>
    <div class="card"><h3>This week's hours</h3><div class="tablewrap" style="border:0"><table class="hours"><tbody>
      ${c.week.map(d => `<tr class="${d.today ? "today" : ""}"><td>${esc(d.weekday)}${d.today ? " (today)" : ""}</td><td>${fmtDate(d.date + "T12:00:00").replace(/^\w+, /, "")}</td>
        <td>${d.closed ? `<b>Closed</b>${d.reason && d.reason !== "Closed" ? ` · ${esc(d.reason)}` : ""}` : `${esc(d.opens)} – ${esc(d.closes)}`}</td></tr>`).join("")}
    </tbody></table></div></div>
    <p class="hint">Updates by itself. Shows counts only, never who is working.</p>`;
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


// ---------- E11 · Time away from the desk (US-34 to US-37) ----------

let absKind = "sick";
const STATUS = { pending: "Pending", approved: "Approved", declined: "Declined", cancelled: "Cancelled" };

function initTimeAway() {
  seg($("#absKind"), [{ key: "sick", label: "I'm sick" }, { key: "emergency", label: "Emergency" }], absKind, k => { absKind = k; });
  $("#absDay").value = $("#absDay").min = isoDay();
  $("#offStart").min = $("#offEnd").min = isoDay();
  $("#offStart").addEventListener("change", () => { if (!$("#offEnd").value || $("#offEnd").value < $("#offStart").value) $("#offEnd").value = $("#offStart").value; });

  /** US-34: report sick or an emergency. */
  $("#absForm").addEventListener("submit", async e => {
    e.preventDefault();
    showErr($("#absErr"), "");
    try {
      const r = await api("/api/absences", { method: "POST", body: { kind: absKind, day: $("#absDay").value, starts: $("#absFrom").value, ends: $("#absTo").value, note: $("#absNote").value } });
      $("#absNote").value = "";
      toast(`Sent at ${r.reported_time} ${r.emailed ? "The supervisor has been emailed." : "The supervisor will see it in Time away."}`);
      refreshTimeAway();
    } catch (err) { showErr($("#absErr"), err.message); }
  });

  /** US-35: request time off. */
  $("#offForm").addEventListener("submit", async e => {
    e.preventDefault();
    showErr($("#offErr"), "");
    try {
      const r = await api("/api/time-off", { method: "POST", body: { start: $("#offStart").value, end: $("#offEnd").value, reason: $("#offReason").value } });
      $("#offReason").value = "";
      toast(r.emailed ? "Request sent. The supervisor has been emailed." : "Request sent. It's waiting for a decision.");
      refreshTimeAway();
    } catch (err) { showErr($("#offErr"), err.message); }
  });

  /** US-35 cancel, US-36 approve or decline. */
  $("#v-timeaway").addEventListener("click", async e => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const id = b.dataset.id;
    try {
      if (b.dataset.act === "cancel") {
        await api(`/api/time-off/${id}/cancel`, { method: "POST" });
        toast("Request cancelled.");
      } else {
        const approve = b.dataset.act === "approve";
        const reason = $(`#why-${id}`)?.value || "";
        const r = await api(`/api/time-off/${id}/decision`, { method: "POST", body: { approve, reason } });
        toast(`${approve ? "Approved" : "Declined"} at ${r.decided_time}${r.emailed ? " The assistant has been emailed." : ""}`);
      }
      refreshTimeAway();
    } catch (err) { toast(err.message); }
  });
}

const reqLine = q => `<span class="t">requested ${esc(q.requested_time)}${q.decided_by ? ` · ${esc(STATUS[q.status].toLowerCase())} by ${esc(q.decided_by)} at ${esc(q.decided_time)}` : q.status === "cancelled" && q.decided_time ? ` · cancelled at ${esc(q.decided_time)}` : ""}</span>`;

/** Draw the Time away screen for whoever is signed in. */
export async function refreshTimeAway() {
  if (!isSignedIn()) return;
  let t;
  try { t = await api("/api/time-away"); } catch { return; }

  // US-36: requests waiting for the supervisor or a shift lead.
  $("#taDecideCard").hidden = !t.senior;
  $("#taReportsCard").hidden = !t.senior;
  if (t.senior) {
    const todo = t.to_decide;
    $("#taDecide").innerHTML = todo.length ? todo.map(q => `<div class="tarow">
        <div class="top"><span class="who">${personHTML({ id: q.staff_id, display_name: q.name })}</span><b>${esc(q.dates)}</b></div>
        <div class="q">${esc(q.reason)}</div>${reqLine(q)}
        ${q.own ? `<p class="hint">This is your own request. Another shift lead or the supervisor has to decide it.</p>`
          : `<div class="acts"><input class="input" id="why-${q.id}" maxlength="200" placeholder="Reason (needed to decline)">
             <button class="btn" data-act="decline" data-id="${q.id}">Decline</button>
             <button class="btn primary" data-act="approve" data-id="${q.id}">Approve</button></div>`}</div>`).join("")
      : `<p class="hint">Nothing is waiting for a decision.</p>`;
    // US-34: who reported sick or an emergency, with the time and any note. Senior only.
    $("#taReports").innerHTML = t.reports.length ? t.reports.map(r => `<div class="tarow">
        <div class="top"><span class="who">${personHTML({ id: 0, display_name: r.name })}</span>
          <span class="pill ${r.kind === "sick" ? "warn" : "urgent"}">${esc(r.kind_label)}</span>${r.late ? `<span class="pill declined">After the shift started</span>` : ""}</div>
        <span class="t">${esc(r.shift)} · reported at ${esc(r.reported_time)}</span>${r.note ? `<div class="q">${esc(r.note)}</div>` : ""}</div>`).join("")
      : `<p class="hint">Nobody has reported sick or an emergency this week.</p>`;
  }

  // US-37: who is away in the next 14 days. Names only.
  const busy = t.upcoming.filter(d => d.away.length);
  $("#taUpcoming").innerHTML = busy.length ? busy.map(d => `<div class="dayrow"><span class="d">${esc(d.label[0].toUpperCase() + d.label.slice(1))}${d.label === "today" || d.label === "tomorrow" ? ` <span class="muted" style="font-weight:500">${esc(d.weekday)}</span>` : ""}</span>
      <span class="names">${d.away.map(p => `<span class="pill off_shift">${esc(p.name)}</span>`).join("")}</span></div>`).join("")
    : `<p class="hint">Nobody is off in the next two weeks.</p>`;

  // My own requests (US-35, US-36) and reports (US-34).
  const reqs = t.my_requests.map(q => `<div class="tarow"><div class="top"><b class="who">Time off · ${esc(q.dates)}</b><span class="pill ${q.status}">${STATUS[q.status]}</span></div>
      ${reqLine(q)}${q.decision_reason ? `<div class="q">${q.status === "declined" ? "Why: " : ""}${esc(q.decision_reason)}</div>` : ""}
      ${q.status === "pending" ? `<div class="acts"><button class="btn sm" data-act="cancel" data-id="${q.id}">Cancel request</button></div>` : ""}</div>`);
  const reps = t.my_reports.map(r => `<div class="tarow"><div class="top"><b class="who">${esc(r.kind_label)} · ${esc(r.shift)}</b><span class="pill ok">Sent</span></div>
      <span class="t">reported at ${esc(r.reported_time)}${r.late ? " · after the shift started" : ""}</span></div>`);
  $("#taMine").innerHTML = reqs.length + reps.length ? [...reps, ...reqs].join("") : `<p class="hint">You haven't sent anything yet.</p>`;
}

/** Pending requests for the supervisor's and shift leads' badge. */
export async function timeAwayBadge() {
  try { const t = await api("/api/time-away"); return t.senior ? t.to_decide.filter(q => !q.own).length : 0; } catch { return 0; }
}
