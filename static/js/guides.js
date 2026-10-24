// Feature 3 · Fix guides | Owner: Priyesh Patel
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
import { api } from "./api.js";
import { $, esc, fmtDate, seg, toast } from "./ui.js";

// Product v1 (Deliverable 2): E5 · Find the right fix fast.
// E6 (US-17 write and edit, US-18 flag, US-19 review) comes in Product v2.
export const stories = ["US-14", "US-15", "US-16"];

let types = [];
let pickedType = null;
let openId = null;
let listMode = "type";            // "type" | "search"
const ticks = new Map();          // guide id -> Set of ticked step numbers (US-16: keeps my place)

export function init(settings) {
  types = settings.problem_types;
  pickedType = types[0].key;
  seg($("#gTypes"), types, pickedType, k => { pickedType = k; listMode = "type"; refresh(); });
  $("#gSearchForm").addEventListener("submit", e => { e.preventDefault(); listMode = $("#gSearch").value.trim() ? "search" : "type"; refresh(); });
  $("#gList").addEventListener("click", e => {
    const b = e.target.closest("button[data-g]");
    if (b) openGuide(Number(b.dataset.g));
  });
  $("#gPane").addEventListener("change", e => {
    if (!e.target.matches(".steps input")) return;
    const set = ticks.get(openId) || new Set();
    e.target.checked ? set.add(e.target.value) : set.delete(e.target.value);
    ticks.set(openId, set);
    progress();
  });
}

function item(g) {
  return `<button class="gitem" data-g="${g.id}" aria-current="${g.id === openId}">
    <span><span class="gt">${g.flagged ? "⚠️ " : ""}${esc(g.title)}</span><br>
    <span class="gm">${esc(g.problem_label)} · reviewed ${fmtDate(g.reviewed_at)}</span></span></button>`;
}

/** Top-bar search: show results for `q` the next time the guides screen opens. */
export function search(q) {
  $("#gSearch").value = q;
  listMode = q.trim() ? "search" : "type";
}

export async function refresh() {
  try {
    let rows, message;
    if (listMode === "search") ({ guides: rows, message } = await api(`/api/guides/search?q=${encodeURIComponent($("#gSearch").value)}`));
    else ({ guides: rows, message } = await api(`/api/guides?problem_type=${pickedType}`));
    $("#gList").innerHTML = rows.length ? rows.map(item).join("") : `<div class="empty">${esc(message)}</div>`;
    if (openId) await openGuide(openId, true);
  } catch { /* signed out */ }
}

function progress() {
  const boxes = [...document.querySelectorAll("#gPane .steps input")];
  const done = boxes.filter(b => b.checked).length;
  $("#gProg").textContent = `${done} of ${boxes.length} steps done`;
  $("#gBar").style.width = `${boxes.length ? (done / boxes.length) * 100 : 0}%`;
}

async function openGuide(id, quiet = false) {
  let g;
  try { g = await api(`/api/guides/${id}`); } catch (err) { if (!quiet) toast(err.message); return; }
  openId = id;
  for (const b of document.querySelectorAll("#gList .gitem")) b.setAttribute("aria-current", String(Number(b.dataset.g) === id));
  const set = ticks.get(id) || new Set();
  $("#gPane").innerHTML = `
    ${g.flag ? `<div class="callout bad">⚠️ Flagged as out of date by ${esc(g.flag.by)} on ${fmtDate(g.flag.at)}: ${esc(g.flag.reason)}</div>` : ""}
    <div><span class="chip">${esc(g.problem_label)}</span>
      <h2 style="font-size:26px;margin-top:6px">${esc(g.title)}</h2>
      <p class="hint">Written by ${esc(g.created_by)}${g.edited_by ? ` · last edited by ${esc(g.edited_by)} on ${fmtDate(g.edited_at)}` : ""}
       · reviewed ${fmtDate(g.reviewed_at)}${g.reviewed_by ? ` by ${esc(g.reviewed_by)}` : ""}</p></div>
    ${g.before_you_start ? `<div class="callout warn"><b>Before you start:</b> ${esc(g.before_you_start)}</div>` : ""}
    <div class="stack" style="gap:6px"><div class="hint" id="gProg"></div><div class="progress"><div id="gBar"></div></div></div>
    <ol class="steps">${g.steps.map((s, i) => `<li><label><input type="checkbox" value="${i + 1}"${set.has(String(i + 1)) ? " checked" : ""}><span>${esc(s)}</span></label></li>`).join("")}</ol>
    <div class="toolbar"><button class="btn" id="gReset">Start again</button></div>`;
  progress();
  $("#gReset").onclick = () => { ticks.delete(id); openGuide(id); };
}
