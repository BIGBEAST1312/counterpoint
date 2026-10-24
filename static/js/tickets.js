// Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
// AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
import { api } from "./api.js";
import { $, esc, fmtDur, ms, seg, showErr, toast } from "./ui.js";

// Product v1 (Deliverable 2): E3 · Write tickets while they're fresh.
// E4 (US-10 to US-12 handover notes, US-13 follow-ups) comes in Product v2.
export const stories = ["US-07", "US-08", "US-09"];

const OUTCOMES = ["Solved", "Escalated", "Student returning"];
let outcome = "";
let list = "unraised";
let editing = null;   // draft id being edited (US-07 test 4)

export function init(settings) {
  $("#dType").innerHTML = settings.problem_types.map(t => `<option value="${esc(t.key)}">${esc(t.label)}</option>`).join("");
  seg($("#dOutcome"), OUTCOMES.map(o => ({ key: o, label: o })), outcome, k => { outcome = k; });

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
    }
  } catch (err) { toast(err.message); }
}

function draftCard(d) {
  const age = fmtDur(Date.now() - ms(d.created_at));
  let acts = `<button class="btn sm" data-act="copy" data-id="${d.id}">Copy</button>`;
  if (!d.locked) acts += `<button class="btn sm" data-act="edit" data-id="${d.id}">Edit</button>
      <input class="input" name="tdx" inputmode="numeric" placeholder="TeamDynamix #" aria-label="TeamDynamix number">
      <button class="btn sm primary" data-act="tdx" data-id="${d.id}">Mark raised</button>`;
  return `<article class="dcard" data-draft="${esc(JSON.stringify(d))}">
    <header><b>${esc(d.summary)}</b><span class="pill ${d.outcome === "Solved" ? "ok" : "warn"}">${esc(d.outcome)}</span></header>
    <div class="hint">${esc(d.author)} · drafted ${age} ago${d.tdx_number ? ` · TeamDynamix <b>${esc(d.tdx_number)}</b>` : ""}</div>
    <pre class="ttext">${esc(d.text)}</pre>
    <div class="acts">${acts}</div></article>`;
}

export async function refreshDrafts() {
  const url = { unraised: "/api/drafts?raised=false", raised: "/api/drafts?raised=true" }[list];
  let rows, mine;
  try { [rows, mine] = await Promise.all([api(url), api("/api/drafts/reminder")]); } catch { return; }
  const empty = { unraised: "Every draft has been raised in TeamDynamix.", raised: "No raised drafts yet." }[list];
  // US-09 test 3: remind me how many of my own drafts still need a TeamDynamix number.
  const reminder = list === "unraised" && mine.message ? `<div class="callout warn">${esc(mine.message)} Raise them before you leave.</div>` : "";
  $("#draftList").innerHTML = reminder + (rows.length ? rows.map(draftCard).join("") : `<div class="empty"><strong>All clear</strong>${empty}</div>`);
}
