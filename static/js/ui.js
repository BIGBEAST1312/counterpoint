// Shared UI helpers | Owner: Priyesh Patel, owned by no feature
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const MIN = 60000;

/** Escape text before putting it inside innerHTML. Anything a person typed must go through this. */
export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const ms = iso => (iso ? Date.parse(iso) : null);

export function fmtDur(millis) {
  if (millis == null || !isFinite(millis)) return "—";
  const m = Math.round(millis / MIN);
  if (m < 1) return "<1 min";
  if (m < 60) return m + " min";
  const h = Math.floor(m / 60), r = m % 60;
  return h + " h" + (r ? " " + r + " min" : "");
}
export const fmtMin = minutes => (minutes == null ? "—" : fmtDur(minutes * MIN));
/** Wait estimates are rough, so show them rounded up to 5 minutes. */
export const fmtEst = minutes => (minutes === 0 ? "Next up" : "~" + fmtDur(Math.ceil(minutes / 5) * 5 * MIN));
export const fmtClock = t => new Date(t).toLocaleTimeString("en-CA", { hour: "numeric", minute: "2-digit" });
export const fmtDate = t => new Date(t).toLocaleDateString("en-CA", { weekday: "long", month: "short", day: "numeric" });
export const fmtShortDate = d => new Date(d + "T12:00:00").toLocaleDateString("en-CA", { month: "short", day: "numeric" });
export const dayKey = t => new Date(t).toDateString();
/** Big-number tiles: shrink the unit so the number stands out. */
export const unit = s => String(s).replace(" min", "<small> min</small>");

/** Wait severity for colour: 0 fine, 1 over 15 min, 2 over 30 min. */
export const severity = millis => (millis >= 30 * MIN ? 2 : millis >= 15 * MIN ? 1 : 0);

/** A person chip: coloured initial + name. `agent` is {id, display_name} from the API. */
export function personHTML(agent, withAvatar = true) {
  if (!agent) return `<span class="person muted">Unassigned</span>`;
  const initial = esc((agent.display_name || "?").trim().charAt(0).toUpperCase());
  const hue = (agent.id * 67) % 360;
  return `<span class="person">${withAvatar ? `<span class="av" style="--h:${hue}" aria-hidden="true">${initial}</span>` : ""}<span>${esc(agent.display_name)}</span></span>`;
}

let toastTimer;
export function toast(message) {
  const t = $("#toast");
  t.textContent = message;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2800);
}

export function setBanner(text) {
  const b = $("#banner");
  b.textContent = text || "";
  b.hidden = !text;
}

/** Re-render without losing the cursor in a text box that gets rebuilt. */
export function keepFocus(render) {
  const active = document.activeElement, id = active && active.id;
  let start, end;
  try { start = active.selectionStart; end = active.selectionEnd; } catch { /* not a text field */ }
  render();
  if (id) {
    const el = document.getElementById(id);
    if (el && el !== active) { el.focus(); try { if (start != null) el.setSelectionRange(start, end); } catch { /* ignore */ } }
  }
}

/** Every 15 s, update elements marked data-since="<ISO time>" to show elapsed time. */
export function startTicker() {
  setInterval(() => {
    const now = Date.now();
    for (const el of $$("[data-since]")) {
      const elapsed = now - Date.parse(el.dataset.since);
      el.textContent = fmtDur(elapsed);
      const row = el.hasAttribute("data-sev-row") && el.closest(".wrow");
      if (row) row.dataset.sev = severity(elapsed);
    }
    for (const el of $$("[data-clock]")) el.textContent = fmtClock(now);
  }, 15000);
}

/** Pressed-state button group: seg(container, items, current, onPick). items = [{key, label}]. */
export function seg(container, items, current, onPick) {
  container.innerHTML = items.map(i => `<button type="button" data-k="${esc(i.key)}" aria-pressed="${i.key === current}">${esc(i.label)}</button>`).join("");
  container.onclick = e => {
    const b = e.target.closest("button[data-k]");
    if (!b) return;
    for (const x of container.children) x.setAttribute("aria-pressed", String(x === b));
    onPick(b.dataset.k);
  };
}

export function showErr(el, message) { el.textContent = message || ""; el.hidden = !message; }

/** Local date as YYYY-MM-DD for <input type=date>. */
export const isoDay = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
