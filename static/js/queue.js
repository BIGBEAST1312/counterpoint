// Feature 1 · Walk-up queue: kiosk, lobby screen, counter panel | Owner: Mohit Sawant
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
import { api } from "./api.js";
import { $, esc, fmtClock, fmtDur, ms, severity, showErr, toast } from "./ui.js";

// Stories built in this file (E1 + E2). main.js shows the parts of the page marked with these.
export const stories = ["US-01", "US-02", "US-03", "US-04", "US-05", "US-06"];

let types = {};
let counters = [];
let lastTop = null;
const COUNTER_KEY = "counterpoint.counter";

export function init(settings) {
  types = Object.fromEntries(settings.problem_types.map(t => [t.key, t.label]));
  counters = settings.counters;

  // Kiosk: check in (US-01, US-02)
  $("#ciTypes").innerHTML = settings.problem_types.map(t =>
    `<label><input type="radio" name="ptype" value="${esc(t.key)}">${esc(t.label)}</label>`).join("");
  $("#ciForm").addEventListener("submit", async e => {
    e.preventDefault();
    showErr($("#ciErr"), "");
    const picked = $("input[name=ptype]:checked");
    try {
      const r = await api("/api/visits", { method: "POST", body: { first_name: $("#ciName").value, problem_type: picked ? picked.value : "" } });
      $("#ciForm").hidden = true;
      $("#ciDone").hidden = false;
      $("#ciDone").innerHTML = `<div class="lbl">Your ticket</div><div class="tnum">${esc(r.ticket)}</div>
        <p><b>${r.place === 1 ? "You're first in line." : `You're number ${r.place} in line.`}</b> ${esc(r.message)}</p>
        <p class="muted">Have a seat. Watch the lobby screen for <b>${esc(r.ticket)}</b> and the counter to go to.</p>`;
      setTimeout(resetKiosk, 15000);   // clear the screen for the next student
    } catch (err) { showErr($("#ciErr"), err.message); }
  });

  // Kiosk: check my place / leave the line (US-03, US-04)
  const ticketNo = () => parseInt($("#placeNo").value.replace(/\D/g, ""), 10);
  $("#placeForm").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      const r = await api(`/api/visits/place?ticket_no=${ticketNo() || 0}`);
      $("#placeOut").textContent = r.place ? `${r.ticket}: you're number ${r.place} in line. ${r.message}`
        : r.status === "called" || r.status === "serving" ? `${r.ticket} has been called to ${r.counter}.` : `${r.ticket} is no longer in the line.`;
    } catch (err) { $("#placeOut").textContent = err.message; }
  });
  $("#leaveBtn").addEventListener("click", async () => {
    try {
      const r = await api("/api/visits/leave", { method: "POST", body: { ticket_no: ticketNo() || 0, first_name: $("#placeName").value } });
      $("#placeOut").textContent = `${r.ticket} has left the line. Thanks for letting us know.`;
      $("#placeNo").value = $("#placeName").value = "";
    } catch (err) { $("#placeOut").textContent = err.message; }
  });

  // Counter panel (US-04, US-06)
  let saved = null;
  try { saved = localStorage.getItem(COUNTER_KEY); } catch { /* private mode */ }
  $("#counterSel").innerHTML = counters.map(c => `<option${c === saved ? " selected" : ""}>${esc(c)}</option>`).join("");
  $("#counterSel").addEventListener("change", () => { try { localStorage.setItem(COUNTER_KEY, $("#counterSel").value); } catch { /* ignore */ } });
  $("#callNext").addEventListener("click", async () => {
    try {
      const v = await api("/api/queue/call-next", { method: "POST", body: { counter: $("#counterSel").value } });
      toast(`Called ${v.ticket} (${v.first_name}) to ${v.counter}`);
      refreshCounter();
    } catch (err) { toast(err.message); }
  });
  $("#atList").addEventListener("click", async e => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    try { await api(`/api/visits/${b.dataset.id}/${b.dataset.act}`, { method: "POST" }); refreshCounter(); }
    catch (err) { toast(err.message); }
  });
}

function resetKiosk() {
  $("#ciForm").reset();
  $("#ciForm").hidden = false;
  $("#ciDone").hidden = true;
  showErr($("#ciErr"), "");
}

export async function refreshKiosk() {
  try {
    const s = await api("/api/queue/summary");
    $("#ciWait").textContent = s.estimate_minutes == null ? "Unknown" : s.estimate_minutes === 0 ? "Next up" : `~${s.estimate_minutes} min`;
    $("#ciAhead").textContent = s.waiting === 1 ? "1 person waiting" : `${s.waiting} people waiting`;
  } catch { /* offline banner covers it */ }
}

export async function refreshLobby() {
  let calls = [];
  try { calls = await api("/api/lobby"); } catch { return; }
  const top = calls[0] ? calls[0].ticket : null;
  const fresh = top && top !== lastTop;
  lastTop = top;
  $("#lobby").innerHTML = `<div class="lobby-head"><h2>Now calling</h2><div class="lobby-clock" data-clock>${fmtClock(Date.now())}</div></div>
    <div class="lobby-card">${calls.length ? calls.map((c, i) => `<div class="callrow${i === 0 && fresh ? " fresh" : ""}">
      <span class="n">${esc(c.ticket)}</span><span class="to">${c.missed ? "missed" : "→ " + esc(c.counter)}</span></div>`).join("")
      : `<p class="lobby-foot">Nobody has been called yet today.</p>`}</div>
    <p class="lobby-foot">When your number appears, go to the counter shown. If you miss your call for <b>5 minutes</b>, check in again at the kiosk.</p>`;
}

export async function refreshCounter() {
  let q;
  try { q = await api("/api/queue"); } catch { return; }
  $("#wCount").textContent = q.waiting.length;
  $("#wEst").textContent = q.estimate_minutes == null ? "" : `New arrivals wait ~${q.estimate_minutes} min`;
  $("#waitList").innerHTML = q.waiting.length ? q.waiting.map(v => {
    const waited = Date.now() - ms(v.arrived_at);
    return `<li class="wrow" data-sev="${severity(waited)}"><div class="stub">${esc(v.ticket)}</div>
      <div class="wbody"><div class="wname">${esc(v.first_name)}</div><div><span class="chip">${esc(types[v.problem_type] || v.problem_type)}</span></div></div>
      <div class="wside"><span class="waited" data-since="${esc(v.arrived_at)}" data-sev-row>${fmtDur(waited)}</span><span class="muted" style="font-size:12px">since ${fmtClock(v.arrived_at)}</span></div></li>`;
  }).join("") : `<li class="empty"><strong>Nobody waiting</strong>New check-ins appear here.</li>`;
  $("#atList").innerHTML = q.at_counters.length ? q.at_counters.map(v => `<div class="scard"><div class="shead">
      <div class="stub">${esc(v.ticket)}</div><div class="wbody"><div class="wname">${esc(v.first_name)}</div>
      <div class="wdetail">${v.status === "called" ? `Called at ${fmtClock(v.called_at)}, not here yet` : "At the counter"}</div></div>
      <span class="station">${esc(v.counter)}</span></div>
      <div class="sbody"><div class="sacts">
        ${v.status === "called" ? `<button class="btn" data-act="here" data-id="${v.id}">Student's here</button>` : ""}
        <button class="btn primary" data-act="done" data-id="${v.id}">Done</button></div></div></div>`).join("")
    : `<div class="empty"><strong>Both counters free</strong>Press Call next.</div>`;
}
