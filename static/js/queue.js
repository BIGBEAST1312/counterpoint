// Feature 1 (E1): kiosk check-in, wait estimate and leave the line | Owner: Mohit Sawant
import { api } from "./api.js";
import { $, esc, showErr } from "./ui.js";
export const stories = ["US-01", "US-02", "US-03"];

export function init(settings) {
  // US-01 and US-02: check in and see the place and wait
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
        <p><b>${r.place === 1 ? "You're first in line." : `You're number ${r.place} in line.`}</b> ${esc(r.message)}</p>`;
      setTimeout(resetKiosk, 15000);   // clear the screen for the next student
    } catch (err) { showErr($("#ciErr"), err.message); }
  });

  // US-02 and US-03: check my place, leave the line
  const ticketNo = () => parseInt($("#placeNo").value.replace(/\D/g, ""), 10) || 0;
  $("#placeForm").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      const r = await api(`/api/visits/place?ticket_no=${ticketNo()}`);
      $("#placeOut").textContent = r.place ? `${r.ticket}: you're number ${r.place} in line. ${r.message}`
        : r.status === "called" || r.status === "serving" ? `${r.ticket} has been called to ${r.counter}.` : `${r.ticket} is no longer in the line.`;
    } catch (err) { $("#placeOut").textContent = err.message; }
  });
  $("#leaveBtn").addEventListener("click", async () => {
    try {
      const r = await api("/api/visits/leave", { method: "POST", body: { ticket_no: ticketNo(), first_name: $("#placeName").value } });
      $("#placeOut").textContent = `${r.ticket} has left the line. Thanks for letting us know.`;
      $("#placeNo").value = $("#placeName").value = "";
    } catch (err) { $("#placeOut").textContent = err.message; }
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

// Lobby screen and counter panel belong to the next epic (call next, lobby, done); kept so main.js still loads.
export async function refreshLobby() {}
export async function refreshCounter() {}
