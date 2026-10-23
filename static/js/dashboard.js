// Shared · Dashboard | Built by Haryan Patel. Owns no data: it only reads each feature's own API.
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
import { api, ApiError } from "./api.js";
import { current, setMyStatus } from "./auth.js";
import { $, esc, fmtClock, personHTML, toast } from "./ui.js";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ARROW = `<svg viewBox="0 0 24 24"><path d="M7 17 17 7M9 7h8v8"/></svg>`;
let firstPaint = true;
let tick = null;

// A feature that isn't merged yet (or a screen this person can't see) answers with an error:
// treat that as "no data" and leave its card off the dashboard.
const get = url => api(url).catch(() => null);

export async function refresh() {
  const me = current();
  if (!me) return;
  $("#dHello").textContent = `Hello, ${me.display_name}`;
  const [queue, board, drafts, follow, handover, week, cov, lobby, mine] = await Promise.all([
    get("/api/queue"), get("/api/status/board"), get("/api/drafts?raised=false&mine=true"), get("/api/followups"),
    get("/api/handover"), get("/api/report/week"), get("/api/coverage"), get("/api/lobby"), get("/api/status/me")]);
  if (mine) setMyStatus(mine);

  const stat = (cls, title, val, sub, href) => `<a class="stat ${cls}" href="${href}">
      <div class="top"><span>${title}</span><span class="go" aria-hidden="true">${ARROW}</span></div>
      <div class="val" data-count="${val}">${val}</div><div class="sub">${esc(sub)}</div></a>`;

  // Top row: one number per feature that has answered.
  const stats = [];
  if (queue) {
    const est = queue.estimate_minutes != null ? `New arrivals wait about ${queue.estimate_minutes} min` : "Wait can't be estimated right now";
    stats.push(stat("hero", "Waiting now", queue.waiting.length, est, "#counter"));
  }
  if (board) stats.push(stat("", "On desk", board.on_desk.length, board.away.length ? `${board.away.length} away right now` : "Nobody is away", "#coverage"));
  if (drafts) stats.push(stat("", "My drafts to raise", drafts.length,
    follow ? (follow.length ? `${follow.length} escalation${follow.length === 1 ? "" : "s"} to follow up` : "No escalations waiting") : "Not yet raised in TeamDynamix", "#tickets"));
  if (handover) {
    const urgent = handover.notes.filter(n => n.urgent).length;
    stats.push(stat("", "Open handover notes", handover.notes.length, urgent ? `${urgent} marked urgent` : "Nothing urgent", "#handover"));
  }

  // Cards below, in the order they appear when every feature is merged.
  const cards = [];
  if (week) cards.push(walkUpsCard(week));
  if (cov) {
    const word = { open: "Open", unattended: "Unattended", closed: "Closed" }[cov.state];
    cards.push(`<div class="card desknow ${cov.state}"><h3>Desk right now</h3>
        <h2>${word}</h2><p class="hint" style="font-size:14px">${esc(cov.message)}</p>
        ${cov.back_message ? `<p class="hint"><b>${esc(cov.back_message)}</b></p>` : ""}
        ${board && board.break_suggestion ? `<div class="callout good" style="font-size:13.5px">☕ ${esc(board.break_suggestion.message)}</div>` : ""}
        <a class="btn" href="#coverage" style="justify-self:start">Open coverage</a></div>`);
  }
  if (lobby) cards.push(`<div class="card"><div class="chead"><h3>Recent calls</h3><a class="btn sm" href="#lobby">Lobby screen</a></div>
        <div class="mini">${lobby.length ? lobby.map(c => `<div class="row"><b style="font-size:20px;letter-spacing:-.03em">${esc(c.ticket)}</b>
          <span></span><span class="pill ${c.missed ? "warn" : "ok"}">${c.missed ? "Missed" : esc(c.counter)}</span></div>`).join("")
          : `<p class="hint">Nobody has been called yet today.</p>`}</div></div>`);
  if (board) {
    const team = [...board.on_desk.map(p => ({ ...p, status: "on_desk", label: "On desk" })), ...board.away];
    cards.push(`<div class="card"><div class="chead"><h3>Team on shift</h3><a class="btn sm" href="#coverage">Coverage</a></div>
        <div class="mini">${team.length ? team.map(p => `<div class="row">${personHTML({ id: p.staff_id, display_name: p.name })}
          <span class="t">${p.status === "on_desk" ? `since ${fmtClock(p.since)}` : p.back_at ? `back at ${fmtClock(p.back_at)}` : `since ${fmtClock(p.since)}`}</span>
          <span class="pill ${p.status}">${esc(p.label)}</span></div>`).join("") : `<p class="hint">Nobody has started a shift yet.</p>`}</div></div>`);
  }
  if (week) cards.push(servedCard(week));
  if (mine) cards.push(timerCard(mine));

  // With every feature merged there are 4 numbers and 6 cards in two rows of 3.
  // While some are missing, the cards flow into one grid that fits however many there are.
  const full = stats.length === 4 && cards.length === 6;
  $("#dash").innerHTML = (stats.length ? `<div class="stats enter${full ? "" : " fit"}">${stats.join("")}</div>` : "")
    + (full ? `<div class="dgrid" style="margin-top:16px">${cards.slice(0, 3).join("")}</div>
               <div class="dgrid b" style="margin-top:16px">${cards.slice(3).join("")}</div>`
       : cards.length ? `<div class="dgrid fit" style="margin-top:16px">${cards.join("")}</div>` : "")
    + (!stats.length && !cards.length ? `<div class="empty"><strong>Nothing to show yet</strong>Cards appear here as each feature is merged.</div>` : "");

  wireTimer(mine);
  if (firstPaint) {   // one entrance: bars grow, gauge sweeps, numbers count up
    requestAnimationFrame(() => requestAnimationFrame(() => {
      document.querySelectorAll("#dash .pbar").forEach(b => { b.style.height = b.dataset.h + "%"; });
      const g = document.querySelector("#dash .g-val"); if (g) g.style.strokeDashoffset = g.dataset.off;
      document.querySelectorAll("#dash [data-count]").forEach(countUp);
    }));
    firstPaint = false;
  }
}

/** Walk-ups this week, one pill per day. Striped = day not reached yet. */
function walkUpsCard(week) {
  const perDay = week.heatmap.rows.map(r => r.counts.reduce((a, b) => a + b, 0));
  const todayIdx = (new Date().getDay() + 6) % 7;
  const max = Math.max(...perDay, 1);
  const pills = perDay.map((n, i) => {
    const future = i > todayIdx, isToday = i === todayIdx;
    const h = future ? 55 : Math.max(14, Math.round((n / max) * 100));
    const tip = (isToday || n === max) && !future && n ? `<span class="tip">${n}</span>` : "";
    const kind = future ? " future" : !n ? " zero" : isToday ? " light" : "";
    return `<div class="pcol${isToday ? " today" : ""}"><div class="ptrack"><div class="pbar${kind}" style="height:${firstPaint ? 0 : h}%" data-h="${h}">${tip}</div></div><span class="d">${DAYS[i]}</span></div>`;
  }).join("");
  const total = perDay.reduce((a, b) => a + b, 0);
  return `<div class="card"><div class="chead"><h3>Walk-ups this week</h3><span class="muted" style="font-size:13px">${total} so far</span></div>
      <div class="pills">${pills}</div></div>`;
}

/** Served this week, as a half-circle gauge. */
function servedCard(week) {
  const t = week.totals;
  const pct = t.walk_ups ? Math.round((t.served / t.walk_ups) * 100) : 0;
  const arc = Math.PI * 80;   // half circle, r = 80
  return `<div class="card"><h3>Served this week</h3>
      <div class="gauge"><svg viewBox="0 0 200 112" aria-hidden="true">
        <path class="g-track" d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke-width="22" stroke-linecap="round"/>
        <path class="g-val" d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke-width="22" stroke-linecap="round"
          stroke-dasharray="${arc}" stroke-dashoffset="${firstPaint ? arc : arc * (1 - pct / 100)}" data-off="${arc * (1 - pct / 100)}"/></svg>
        <div class="g-num"><b>${pct}%</b><span>${t.walk_ups ? `${t.served} of ${t.walk_ups} walk-ups` : "No walk-ups yet"}</span></div></div>
      <div class="legend"><span><i style="background:var(--accent)"></i>Served</span><span><i style="background:var(--surface-2);border:1px solid var(--line)"></i>Left or missed their call</span></div></div>`;
}

function countUp(el) {
  const end = Number(el.dataset.count), start = performance.now();
  if (!end || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const step = now => { const k = Math.min(1, (now - start) / 650); el.textContent = Math.round(end * (1 - (1 - k) ** 3)); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}

const PLAY = `<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>`;
const PAUSE = `<svg viewBox="0 0 24 24"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>`;
const STOP = `<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>`;

/** "My time on desk": counts up while I'm on desk. Pause = go on break, stop = end my shift. */
function timerCard(mine) {
  const s = mine ? mine.status : "off_shift";
  const on = s === "on_desk", off = s === "off_shift";
  const sub = on ? `On desk since ${fmtClock(mine.since)}` : off ? "You're off shift" : `${esc(mine.label)} since ${fmtClock(mine.since)}${mine.back_at ? `, back at ${fmtClock(mine.back_at)}` : ""}`;
  return `<div class="card timer"><h3>My time on desk</h3>
    <div class="clock" id="dClock" data-since="${on ? esc(mine.since) : ""}">${on ? "00:00:00" : "--:--:--"}</div>
    <div class="tsub">${sub}</div>
    <div class="tacts">
      ${on ? `<button class="round" data-go="on_break" aria-label="Go on break">${PAUSE}</button>`
           : `<button class="round" data-go="on_desk" aria-label="${off ? "Start my shift" : "Back on desk"}">${PLAY}</button>`}
      <button class="round stop" data-go="off_shift" aria-label="End my shift"${off ? " disabled" : ""}>${STOP}</button>
      <small>${on ? "Pause for a break, or end your shift" : off ? "Start your shift" : "Back on desk"}</small>
    </div></div>`;
}

function wireTimer() {
  clearInterval(tick);
  const clock = $("#dClock");
  const draw = () => {
    if (!clock || !clock.dataset.since) return;
    const s = Math.max(0, Math.floor((Date.now() - Date.parse(clock.dataset.since)) / 1000));
    clock.textContent = [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map(n => String(n).padStart(2, "0")).join(":");
  };
  draw();
  tick = setInterval(draw, 1000);
  document.querySelectorAll("#dash .timer [data-go]").forEach(b => b.addEventListener("click", () => go(b.dataset.go)));
}

async function go(status, confirmEmpty = false) {
  try {
    await api("/api/status/me", { method: "PATCH", body: { status, confirm_empty: confirmEmpty } });
    refresh();
  } catch (err) {
    if (err instanceof ApiError && err.status === 409 && confirm(`${err.message}\n\nLeave the desk anyway?`)) return go(status, true);
    if (!(err instanceof ApiError && err.status === 409)) toast(err.message);
  }
}
