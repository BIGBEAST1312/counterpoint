// Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
// AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
import { api } from "./api.js";
import { $, esc, fmtClock, fmtDate, fmtDur, ms, seg, showErr, toast } from "./ui.js";

// Stories built in this file (E3 + E4). main.js shows the parts of the page marked with these.
export const stories = ["US-07", "US-08", "US-09", "US-10", "US-11", "US-12", "US-13"];

const OUTCOMES = ["Solved", "Escalated", "Student returning"];
const CATEGORIES = ["Follow-up", "Equipment", "FYI"];
let outcome = "";
let category = "FYI";
let list = "unraised";
let noteList = "open";
let editing = null;   // draft id being edited (US-07 test 4)

export function init(settings) {
  $("#dType").innerHTML = settings.problem_types.map(t => `<option value="${esc(t.key)}">${esc(t.label)}</option>`).join("");
  seg($("#dOutcome"), OUTCOMES.map(o => ({ key: o, label: o })), outcome, k => { outcome = k; });
  seg($("#hoCat"), CATEGORIES.map(c => ({ key: c, label: c })), category, k => { category = k; });

  $("#draftForm").addEventListener("submit", async e => {
    e.preventDefault();
    showErr($("#dErr"), "");
    const body = { problem_type: $("#dType").value, reported: $("#dReported").value, what_i_did: $("#dDid").value, outcome };
    try {
      await api(editing ? `/api/drafts/${editing}` : "/api/drafts", { method: editing ? "PUT" : "POST", body });
      toast(editing ? "Draft updated" : "Draft saved. Copy it into TeamDynamix.");
      clearForm();
      list = "unraised";
      for (const b of $("#draftSeg").children) b.setAttribute("aria-pressed", String(b.dataset.list === list));
      refreshDrafts();
    } catch (err) { showErr($("#dErr"), err.message); }
  });
  $("#dCancel").addEventListener("click", clearForm);
  $("#draftSeg").addEventListener("click", e => {
    const b = e.target.closest("button[data-list]");
    if (!b) return;
    list = b.dataset.list;
    for (const x of $("#draftSeg").children) x.setAttribute("aria-pressed", String(x === b));
    refreshDrafts();
  });
  $("#draftList").addEventListener("click", onDraftAction);

  $("#hoText").addEventListener("input", () => { $("#hoCount").textContent = `${$("#hoText").value.length} / 500`; });
  $("#hoForm").addEventListener("submit", async e => {
    e.preventDefault();
    showErr($("#hoErr"), "");
    try {
      await api("/api/handover", { method: "POST", body: { text: $("#hoText").value, category, urgent: $("#hoUrgent").checked } });
      $("#hoForm").reset(); $("#hoCount").textContent = "0 / 500";
      toast("Note saved for the next shift");
      refreshHandover();
    } catch (err) { showErr($("#hoErr"), err.message); }
  });
  $("#hoSeg").addEventListener("click", e => {
    const b = e.target.closest("button[data-list]");
    if (!b) return;
    noteList = b.dataset.list;
    for (const x of $("#hoSeg").children) x.setAttribute("aria-pressed", String(x === b));
    refreshHandover();
  });
  $("#noteList").addEventListener("click", async e => {
    const b = e.target.closest("button[data-resolve]");
    if (!b) return;
    try { await api(`/api/handover/${b.dataset.resolve}/resolve`, { method: "PATCH" }); refreshHandover(); }
    catch (err) { toast(err.message); }
  });
}

function clearForm() {
  editing = null;
  $("#draftForm").reset();
  outcome = "";
  for (const b of $("#dOutcome").children) b.setAttribute("aria-pressed", "false");
  $("#dSubmit").textContent = "Make draft";
  $("#dCancel").hidden = true;
  showErr($("#dErr"), "");
}

async function onDraftAction(e) {
  const b = e.target.closest("button[data-act]");
  if (!b) return;
  const id = b.dataset.id, card = b.closest(".dcard");
  try {
    if (b.dataset.act === "copy") {
      await navigator.clipboard.writeText(card.querySelector(".ttext").textContent);
      toast("Copied. Paste it into TeamDynamix.");
    } else if (b.dataset.act === "tdx") {
      await api(`/api/drafts/${id}/tdx`, { method: "PATCH", body: { tdx_number: card.querySelector("input[name=tdx]").value } });
      toast("Marked as raised"); refreshDrafts();
    } else if (b.dataset.act === "edit") {
      const d = JSON.parse(card.dataset.draft);
      editing = d.id;
      $("#dType").value = d.problem_type; $("#dReported").value = d.reported; $("#dDid").value = d.what_i_did;
      outcome = d.outcome;
      for (const x of $("#dOutcome").children) x.setAttribute("aria-pressed", String(x.dataset.k === outcome));
      $("#dSubmit").textContent = "Save changes"; $("#dCancel").hidden = false;
      $("#dReported").focus();
    } else if (b.dataset.act === "follow") {
      const note = card.querySelector("input[name=fnote]").value;
      await api(`/api/drafts/${id}/followed-up`, { method: "POST", body: { note } });
      toast("Follow-up ticked off"); refreshDrafts();
    }
  } catch (err) { toast(err.message); }
}

function draftCard(d) {
  const age = fmtDur(Date.now() - ms(d.created_at));
  let acts = `<button class="btn sm" data-act="copy" data-id="${d.id}">Copy</button>`;
  if (!d.locked) acts += `<button class="btn sm" data-act="edit" data-id="${d.id}">Edit</button>
      <input class="input" name="tdx" inputmode="numeric" placeholder="TeamDynamix #" aria-label="TeamDynamix number">
      <button class="btn sm primary" data-act="tdx" data-id="${d.id}">Mark raised</button>`;
  if (list === "followups") acts = `<input class="input" name="fnote" placeholder="What was done" aria-label="Follow-up note" style="width:220px">
      <button class="btn sm primary" data-act="follow" data-id="${d.id}">Followed up</button>`;
  return `<article class="dcard" data-draft="${esc(JSON.stringify(d))}">
    <header><b>${esc(d.summary)}</b><span class="pill ${d.outcome === "Solved" ? "ok" : "warn"}">${esc(d.outcome)}</span></header>
    <div class="hint">${esc(d.author)} · drafted ${age} ago${d.tdx_number ? ` · TeamDynamix <b>${esc(d.tdx_number)}</b>` : ""}</div>
    ${list === "followups" ? "" : `<pre class="ttext">${esc(d.text)}</pre>`}
    <div class="acts">${acts}</div></article>`;
}

export async function refreshDrafts() {
  const url = { unraised: "/api/drafts?raised=false", raised: "/api/drafts?raised=true", followups: "/api/followups" }[list];
  let rows;
  try { rows = await api(url); } catch { return; }
  const empty = { unraised: "Every draft has been raised in TeamDynamix.", raised: "No raised drafts yet.",
                  followups: "No escalations waiting for a follow-up." }[list];
  $("#draftList").innerHTML = rows.length ? rows.map(draftCard).join("") : `<div class="empty"><strong>All clear</strong>${empty}</div>`;
}

export async function refreshHandover() {
  try {
    const open = await api("/api/handover");
    const n = open.my_unraised_drafts;
    $("#hoUnraised").hidden = !n;
    $("#hoUnraised").innerHTML = `You still have <b>${n}</b> draft${n === 1 ? "" : "s"} to raise in TeamDynamix. <a href="#tickets">Open tickets</a>`;
    const notes = noteList === "open" ? open.notes : await api("/api/handover/resolved");
    $("#noteList").innerHTML = notes.length ? notes.map(x => `<article class="note${x.resolved_at ? "" : " open"}">
        <header><span class="who">${esc(x.author)}</span><span>${fmtDate(x.created_at)}, ${fmtClock(x.created_at)}</span>
          <span class="chip">${esc(x.category)}</span>${x.urgent ? `<span class="pill urgent">Urgent</span>` : ""}</header>
        <p>${esc(x.text)}</p>
        <footer>${x.resolved_at ? `Resolved by ${esc(x.resolved_by)} at ${fmtClock(x.resolved_at)}`
          : `<button class="btn sm" data-resolve="${x.id}">Resolve</button>`}</footer></article>`).join("")
      : `<div class="empty"><strong>${noteList === "open" ? "Nothing handed over." : "Nothing resolved this week."}</strong></div>`;
  } catch { /* signed out */ }
}
