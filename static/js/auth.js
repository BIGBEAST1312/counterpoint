// Shared: staff sign-in and the "me" bar | Owner: Priyesh Patel, owned by no feature
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
import { api, session } from "./api.js";
import { $, esc, personHTML, showErr } from "./ui.js";

let me = null;
let myStatus = null;   // set by coverage.js so the header can show it
export const current = () => me;
export const isSignedIn = () => !!me;
export const isSenior = () => !!me && (me.role === "lead" || me.role === "supervisor");

const STATUS_LABEL = { on_desk: "On desk", on_break: "On break", at_lunch: "At lunch", stepped_away: "Stepped away", off_shift: "Off shift" };

export function setMyStatus(s) { myStatus = s; render(); }

export function render() {
  const bar = $("#meBar");
  if (!me) { bar.innerHTML = ""; return; }
  const st = myStatus ? myStatus.status : null;   // null until the coverage feature reports it
  const role = { assistant: "Student assistant", lead: "Shift lead", supervisor: "Desk supervisor" }[me.role] || me.role;
  bar.innerHTML = `${st ? `<a class="pill statusbtn ${st}" href="#coverage" title="Change where I am">${STATUS_LABEL[st]}</a>` : ""}
    ${personHTML(me).replace(/<span>[^<]*<\/span><\/span>$/, "</span>")}
    <span class="who"><b>${esc(me.display_name)}</b><span>${esc(role)}</span></span>`;
  for (const id of ["#notifTab", "#bell"]) { const el = $(id); if (el) el.hidden = false; }   // every staff member sees the feed (US-33 test 4)
}

export async function signOut() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* already signed out */ }
  session.clear(); me = null; window.dispatchEvent(new Event("counterpoint:signed-out"));
}

export async function restore() {
  if (!session.token) return;
  try { me = await api("/api/auth/me"); } catch { me = null; }
}

export function forget() { me = null; myStatus = null; render(); }

export function init({ signedIn }) {
  $("#loginForm").addEventListener("submit", async e => {
    e.preventDefault();
    showErr($("#loginErr"), "");
    try {
      const r = await api("/api/auth/login", { method: "POST", body: { username: $("#loginUser").value, password: $("#loginPass").value } });
      session.set(r.token);
      me = r.staff;
      $("#loginPass").value = "";
      render();
      signedIn();
    } catch (err) { showErr($("#loginErr"), err.message); }
  });
}
