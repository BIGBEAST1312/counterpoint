// Feature 3 · Fix guides | Owner: Priyesh Patel
// AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
import { api } from "./api.js";
import { isSenior } from "./auth.js";
import { $, esc, fmtDate, seg, showErr, toast } from "./ui.js";

// Stories built in this file (E5 + E6). main.js shows the parts of the page marked with these.
export const stories = ["US-14", "US-15", "US-16", "US-17", "US-18", "US-19"];

let types = [];
let pickedType = null;
let openId = null;
let listMode = "type";            // "type" | "search" | "fix"
const ticks = new Map();          // guide id -> Set of ticked step numbers (US-16: keeps my place)

export function init(settings) {
  types = settings.problem_types;
  pickedType = types[0].key;
  seg($("#gTypes"), types, pickedType, k => { pickedType = k; listMode = "type"; refresh(); });
  $("#gSearchForm").addEventListener("submit", e => { e.preventDefault(); listMode = $("#gSearch").value.trim() ? "search" : "type"; refresh(); });
  $("#gNeedsFix").addEventListener("click", () => { listMode = "fix"; refresh(); });
  $("#gNew").addEventListener("click", () => editor(null));
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
    <span class="gm">${esc(g.problem_label)} · reviewed ${fmtDate(g.reviewed_at)}${g.reason ? ` · flagged: ${esc(g.reason)}` : ""}</span></span>
    ${g.needs_review ? `<span class="pill warn">Needs review</span>` : ""}</button>`;
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
    else if (listMode === "fix") { rows = await api("/api/guides/needs-fixing"); message = rows.length ? null : "No guides are flagged."; }
    else ({ guides: rows, message } = await api(`/api/guides?problem_type=${pickedType}`));
    $("#gList").innerHTML = (listMode === "fix" ? `<div class="lbl">Needs fixing, oldest flag first</div>` : "")
      + (rows.length ? rows.map(item).join("") : `<div class="empty">${esc(message)}</div>`);
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
    ${g.flag ? `<div class="callout bad">⚠️ Flagged as out of date by ${esc(g.flag.by)} on ${fmtDate(g.flag.at)}: ${esc(g.flag.reason)}
      <div style="margin-top:8px"><button class="btn sm" id="gFixed">Mark fixed</button></div></div>` : ""}
    <div><span class="chip">${esc(g.problem_label)}</span> ${g.needs_review ? `<span class="pill warn">Needs review</span>` : ""}
      <h2 style="font-size:26px;margin-top:6px">${esc(g.title)}</h2>
      <p class="hint">Written by ${esc(g.created_by)}${g.edited_by ? ` · last edited by ${esc(g.edited_by)} on ${fmtDate(g.edited_at)}` : ""}
       · reviewed ${fmtDate(g.reviewed_at)}${g.reviewed_by ? ` by ${esc(g.reviewed_by)}` : ""}</p></div>
    ${g.before_you_start ? `<div class="callout warn"><b>Before you start:</b> ${esc(g.before_you_start)}</div>` : ""}
    <div class="stack" style="gap:6px"><div class="hint" id="gProg"></div><div class="progress"><div id="gBar"></div></div></div>
    <ol class="steps">${g.steps.map((s, i) => `<li><label><input type="checkbox" value="${i + 1}"${set.has(String(i + 1)) ? " checked" : ""}><span>${esc(s)}</span></label></li>`).join("")}</ol>
    <div class="toolbar"><button class="btn" id="gReset">Start again</button><button class="btn" id="gEdit">Edit guide</button>
      ${g.flag ? "" : `<button class="btn warn" id="gFlag">Flag as out of date</button>`}
      ${isSenior() ? `<button class="btn" id="gReview">Mark reviewed</button>` : ""}</div>
    <form id="gFlagForm" class="dialog" hidden novalidate><div class="field"><label for="gReason">What's wrong?</label>
      <input class="input" id="gReason" maxlength="300" placeholder="e.g. Android 15 menu changed"></div>
      <div class="err" id="gFlagErr" hidden></div><div class="acts"><button class="btn primary" type="submit">Flag guide</button></div></form>`;
  progress();
  $("#gReset").onclick = () => { ticks.delete(id); openGuide(id); };
  $("#gEdit").onclick = () => editor(g);
  if ($("#gFlag")) $("#gFlag").onclick = () => { $("#gFlagForm").hidden = false; $("#gReason").focus(); };
  $("#gFlagForm").onsubmit = async e => {
    e.preventDefault();
    try { await api(`/api/guides/${id}/flag`, { method: "POST", body: { reason: $("#gReason").value } }); refresh(); }
    catch (err) { showErr($("#gFlagErr"), err.message); }
  };
  if ($("#gFixed")) $("#gFixed").onclick = async () => { await api(`/api/guides/${id}/flag/fixed`, { method: "POST" }); refresh(); };
  if ($("#gReview")) $("#gReview").onclick = async () => {
    try { await api(`/api/guides/${id}/reviewed`, { method: "POST" }); toast("Marked as reviewed today"); refresh(); }
    catch (err) { toast(err.message); }
  };
}

function editor(g) {
  let steps = g ? [...g.steps] : [""];
  $("#gPane").innerHTML = `<h2 style="font-size:24px;text-transform:uppercase">${g ? "Edit guide" : "Write a guide"}</h2>
    <div class="field"><label for="eTitle">Title</label><input class="input" id="eTitle" maxlength="120" value="${esc(g ? g.title : "")}"></div>
    <div class="field"><label for="eType">Problem type</label><select class="input" id="eType">${types.map(t => `<option value="${esc(t.key)}"${t.key === (g ? g.problem_type : pickedType) ? " selected" : ""}>${esc(t.label)}</option>`).join("")}</select></div>
    <div class="field"><label for="eBefore">Before you start <span class="muted" style="font-weight:400">(optional)</span></label><textarea class="input" id="eBefore" maxlength="1000">${esc(g ? g.before_you_start : "")}</textarea></div>
    <div class="field"><span style="font-size:13px;font-weight:600">Steps (20 at most)</span><div class="edsteps" id="eSteps"></div>
      <button class="btn sm" type="button" id="eAdd" style="justify-self:start">Add step</button></div>
    <div class="err" id="eErr" hidden></div>
    <div class="toolbar"><button class="btn primary" id="eSave">Save guide</button><button class="btn" id="eCancel">Cancel</button></div>`;
  const draw = () => {
    $("#eSteps").innerHTML = steps.map((s, i) => `<div class="edstep"><span class="n">${i + 1}</span>
      <input class="input" data-i="${i}" value="${esc(s)}" aria-label="Step ${i + 1}">
      <span class="mv"><button class="btn sm" data-up="${i}" aria-label="Move up"${i ? "" : " disabled"}>↑</button>
      <button class="btn sm" data-down="${i}" aria-label="Move down"${i < steps.length - 1 ? "" : " disabled"}>↓</button>
      <button class="btn sm warn" data-del="${i}" aria-label="Remove">✕</button></span></div>`).join("");
  };
  draw();
  $("#eSteps").addEventListener("input", e => { if (e.target.dataset.i) steps[Number(e.target.dataset.i)] = e.target.value; });
  $("#eSteps").addEventListener("click", e => {
    const b = e.target.closest("button");
    if (!b) return;
    const swap = (a, c) => { [steps[a], steps[c]] = [steps[c], steps[a]]; };
    if (b.dataset.up) swap(+b.dataset.up, +b.dataset.up - 1);
    if (b.dataset.down) swap(+b.dataset.down, +b.dataset.down + 1);
    if (b.dataset.del) steps.splice(+b.dataset.del, 1);
    draw();
  });
  $("#eAdd").onclick = () => { steps.push(""); draw(); $(`#eSteps input[data-i="${steps.length - 1}"]`).focus(); };
  $("#eCancel").onclick = () => (g ? openGuide(g.id) : ($("#gPane").innerHTML = `<div class="empty"><strong>Pick a guide</strong></div>`));
  $("#eSave").onclick = async () => {
    const body = { title: $("#eTitle").value, problem_type: $("#eType").value, before_you_start: $("#eBefore").value, steps };
    try {
      const saved = await api(g ? `/api/guides/${g.id}` : "/api/guides", { method: g ? "PUT" : "POST", body });
      toast("Guide saved"); ticks.delete(saved.id);
      pickedType = saved.problem_type; listMode = "type";
      for (const b of $("#gTypes").children) b.setAttribute("aria-pressed", String(b.dataset.k === pickedType));
      openId = saved.id; refresh();
    } catch (err) { showErr($("#eErr"), err.message); }
  };
}
