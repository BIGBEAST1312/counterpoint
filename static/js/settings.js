// Shared · Settings (this device only) | Owner: Priyesh Patel
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
import { current } from "./auth.js";
import { $, esc, personHTML, seg, toast } from "./ui.js";

const ACCENTS = [
  { key: "forest", label: "Forest", color: "#1E5E43" },
  { key: "ocean", label: "Ocean", color: "#1F4E8C" },
  { key: "plum", label: "Plum", color: "#5B3B8C" },
  { key: "ember", label: "Ember", color: "#A84A22" },
];
const THEMES = [{ key: "light", label: "Light" }, { key: "dark", label: "Dark" }, { key: "system", label: "Match my computer" }];
const store = {
  get(k, d) { try { return localStorage.getItem("counterpoint." + k) || d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("counterpoint." + k, v); } catch { /* private mode: still applies for this visit */ } },
};

export function init() {
  drawAccents();
  seg($("#setTheme"), THEMES, store.get("theme", "light"), k => {
    store.set("theme", k);
    if (k === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = k;
    toast(k === "system" ? "Theme now matches your computer" : `Theme set to ${k}`);
  });
}

function drawAccents() {
  const now = store.get("accent", "forest");
  $("#setAccent").innerHTML = ACCENTS.map(a => `<button type="button" class="swatch" data-a="${a.key}" aria-pressed="${a.key === now}">
    <i style="background:${a.color}"></i>${a.label}</button>`).join("");
  $("#setAccent").onclick = e => {
    const b = e.target.closest("[data-a]");
    if (!b) return;
    store.set("accent", b.dataset.a);
    document.documentElement.dataset.accent = b.dataset.a;
    drawAccents();
    toast(`Accent set to ${ACCENTS.find(a => a.key === b.dataset.a).label}`);
  };
}

export function refresh() {
  const me = current();
  if (!me) return;
  const role = { assistant: "Student assistant", lead: "Shift lead", supervisor: "Desk supervisor" }[me.role] || me.role;
  $("#setProfile").innerHTML = `<h3>Profile</h3>
    <div style="display:flex;align-items:center;gap:12px">${personHTML(me, true).replace('class="person"', 'class="person" style="font-size:16px"')}</div>
    <div class="tablewrap"><table><tbody>
      <tr><th>Username</th><td>${esc(me.username)}</td></tr>
      <tr><th>Role</th><td>${esc(role)}</td></tr></tbody></table></div>
    <p class="note-sm">Ask the desk supervisor to change your name or role.</p>`;
}
