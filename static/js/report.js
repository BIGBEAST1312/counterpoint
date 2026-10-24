// Feature 4 · Weekly report & trends | Owner: Haryan Patel
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
import { api } from "./api.js";
import { $, esc, fmtShortDate, isoDay } from "./ui.js";

// Product v1 (Deliverable 2): E7 · Weekly desk report.
// E8 (US-23 compare, US-24 problem types, US-25 CSV) comes in Product v2.
export const stories = ["US-20", "US-21", "US-22"];

let week = null;  // any date in the chosen week (YYYY-MM-DD); null = this week

export function init() {
  $("#rWeek").value = isoDay();
  $("#rWeek").max = isoDay();
  $("#rWeek").addEventListener("change", () => { week = $("#rWeek").value || null; refresh(); });
}

const LABELS = { walk_ups: "Walk-ups", served: "Served", walk_aways: "Walk-aways", median_wait: "Median wait", p90_wait: "90th-percentile wait" };

function tile(key, value, unit = "") {
  return `<div class="tile"><div class="lbl">${LABELS[key]}</div><div class="val">${value ?? "—"}${value != null && unit ? `<small> ${unit}</small>` : ""}</div></div>`;
}

function heat(h) {
  const cols = `grid-template-columns: 44px repeat(${h.hours.length}, minmax(0, 1fr))`;
  const label = hr => (hr % 12 || 12) + (hr < 12 ? "a" : "p");
  const shade = n => (n && h.max ? `background: color-mix(in oklab, var(--accent) ${Math.round(15 + 75 * n / h.max)}%, var(--surface)); color: ${n / h.max > .55 ? "var(--accent-ink)" : "var(--ink)"}` : "background: var(--surface-2); color: var(--muted)");
  return `<div class="heatwrap"><div class="heat" style="${cols}"><span></span>${h.hours.map(x => `<span class="hh">${label(x)}</span>`).join("")}
    ${h.rows.map(r => `<span class="hl">${r.day}</span>${r.counts.map(n => `<span class="c" style="${shade(n)}">${n}</span>`).join("")}`).join("")}</div></div>
    ${h.peak ? `<p class="note-sm">Busiest: <b>${h.peak.day} ${label(h.peak.hour)}–${label(h.peak.hour + 1)}</b> with ${h.peak.count} arrivals.</p>` : ""}`;
}

export async function refresh() {
  let r;
  try { r = await api(`/api/report/week${week ? `?week=${week}` : ""}`); } catch (err) { $("#rBody").innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
  $("#rTitle").textContent = `Week of ${fmtShortDate(r.week_start)} – ${fmtShortDate(r.week_end)}`;
  if (r.empty) { $("#rBody").innerHTML = `<div class="empty"><strong>${esc(r.message)}</strong>Pick another week.</div>`; return; }
  const t = r.totals;
  $("#rBody").innerHTML = `
    <div class="strip">${tile("walk_ups", t.walk_ups)}${tile("served", t.served)}
      ${tile("walk_aways", `${t.walk_aways}<small> (${t.walk_away_pct}%)</small>`)}
      ${tile("median_wait", t.median_wait, "min")}${tile("p90_wait", t.p90_wait, "min")}</div>
    <p class="note-sm">Walk-aways are students who left the line or missed their call. Their time isn't counted in the waits.</p>
    <div class="card"><h3>Busiest hours</h3>${heat(r.heatmap)}</div>`;
}
