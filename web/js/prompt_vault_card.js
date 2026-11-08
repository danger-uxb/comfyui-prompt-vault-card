/*
 * Prompt Vault Card — A Smaller Hammer node for ComfyUI (frontend panel).
 *
 * Shows what the card will hold before you run: each field with where its
 * value comes from (override / wired / traced), an Override tick per field,
 * the generation settings, a tick list of extra settings for the metadata
 * section, the shortname table and the JSON that will be embedded.
 * All resolving is done by the Python side (one source of truth) through
 * /smallerhammer/promptvault/resolve.
 *
 * Copyright (c) 2026 Smaller Hammer - MIT Licence
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "SH_PromptVaultCard";
const ROUTE = "/smallerhammer/promptvault";
const FIELDS = [
  ["positive", "Positive", true],
  ["negative", "Negative", true],
  ["seed", "Seed", false],
  ["width", "Width", false],
  ["height", "Height", false],
  ["ratio", "Ratio", false],
];
const CARD_KEY = { positive: "promptText", negative: "negativePrompt", seed: "seed",
                   width: "width", height: "height", ratio: "ratio" };

const CSS = `
.sh-pv{display:flex;flex-direction:column;gap:6px;height:100%;box-sizing:border-box;padding:4px;
  font:12px/1.35 system-ui,sans-serif;color:var(--input-text,#ddd);--sh-brass:#c9a227;overflow:hidden}
.sh-pv *{box-sizing:border-box}
.sh-pv-bar{display:flex;gap:4px;align-items:center;flex-wrap:wrap}
.sh-pv button{background:var(--comfy-input-bg,#222);color:inherit;border:1px solid var(--border-color,#444);
  border-radius:4px;padding:3px 8px;cursor:pointer;font:inherit}
.sh-pv button:hover{border-color:var(--sh-brass)}
.sh-pv button.pri{border-color:var(--sh-brass);color:var(--sh-brass)}
.sh-pv input[type=text],.sh-pv textarea,.sh-pv select{background:var(--comfy-input-bg,#222);color:inherit;
  border:1px solid var(--border-color,#444);border-radius:4px;padding:3px 6px;font:inherit}
.sh-pv input[type=checkbox]{accent-color:var(--sh-brass);margin:0 4px 0 0;cursor:pointer}
.sh-pv-status{opacity:.7;margin-left:auto;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:50%}
.sh-pv-status.err{color:#e06c6c;opacity:1}
.sh-pv-h{font-weight:600;color:var(--sh-brass);font-size:11px;letter-spacing:.06em;text-transform:uppercase;margin-top:2px}
.sh-pv-scroll{flex:1;min-height:0;overflow:auto;display:flex;flex-direction:column;gap:6px;padding-right:2px}
.sh-pv-scroll>*{flex-shrink:0}
.sh-pv-scroll>.sh-pv-list{flex-shrink:1}
.sh-pv-fields{display:grid;grid-template-columns:70px 1fr auto;gap:3px 8px;align-items:start}
.sh-pv-fields .f{font-weight:600;padding-top:3px}
.sh-pv-fields .v{min-width:0}
.sh-pv-fields .val{font-family:ui-monospace,Consolas,monospace;font-size:11px;white-space:pre-wrap;word-break:break-word;
  max-height:4.2em;overflow:hidden;opacity:.9}
.sh-pv-fields .val.empty{opacity:.45;font-style:italic;font-family:inherit}
.sh-pv-fields .src{font-size:10.5px;opacity:.6}
.sh-pv-fields .src.warn{color:#d48b4a;opacity:1}
.sh-pv-fields .src.ovr{color:var(--sh-brass);opacity:1}
.sh-pv-fields textarea{width:100%;resize:vertical;min-height:52px;font:11px/1.4 ui-monospace,Consolas,monospace}
.sh-pv-fields input[type=text]{width:100%}
.sh-pv-fields label.o{white-space:nowrap;font-size:11px;padding-top:3px;cursor:pointer}
.sh-pv-set{display:grid;grid-template-columns:70px 1fr;gap:2px 8px;font-size:11.5px}
.sh-pv-set .k{opacity:.7}
.sh-pv-set .lv{font-family:ui-monospace,Consolas,monospace;font-size:11px;word-break:break-all}
.sh-pv-list{flex:1 1 auto;min-height:200px;overflow:auto;border:1px solid var(--border-color,#444);
  border-radius:4px;background:var(--comfy-input-bg,#1a1a1a)}
.sh-pv-grp{display:flex;align-items:center;gap:4px;padding:3px 6px;cursor:pointer;position:sticky;top:0;
  background:var(--comfy-menu-bg,#2a2a2a);border-bottom:1px solid var(--border-color,#333)}
.sh-pv-grp .t{font-weight:600}.sh-pv-grp .c{opacity:.55;font-size:11px}.sh-pv-grp .n{margin-left:auto;opacity:.6;font-size:11px}
.sh-pv-row{display:flex;align-items:center;gap:6px;padding:2px 6px 2px 22px;cursor:pointer}
.sh-pv-row:hover{background:rgba(201,162,39,.08)}
.sh-pv-row .k{min-width:90px}
.sh-pv-row .lv{flex:1;opacity:.7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:ui-monospace,monospace}
.sh-pv-row .auto{color:var(--sh-brass);font-size:10.5px;white-space:nowrap}
.sh-pv-row.isauto{opacity:.55;cursor:default}
.sh-pv-notes{color:#d48b4a;font-size:11px}
.sh-pv-out{width:100%;min-height:120px;height:160px;resize:vertical;font:11px/1.4 ui-monospace,Consolas,monospace;white-space:pre}
.sh-pv-dlg{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:10000;display:flex;align-items:center;justify-content:center}
.sh-pv-dlg .box{width:min(820px,94vw);max-height:88vh;display:flex;flex-direction:column;background:var(--comfy-menu-bg,#202020);
  color:var(--fg-color,#ddd);border:1px solid var(--border-color,#444);border-radius:8px;font:13px system-ui,sans-serif}
.sh-pv-dlg .hd,.sh-pv-dlg .ft{padding:10px 14px;display:flex;gap:8px;align-items:center}
.sh-pv-dlg .hd{border-bottom:1px solid var(--border-color,#444)}.sh-pv-dlg .ft{border-top:1px solid var(--border-color,#444);justify-content:flex-end}
.sh-pv-dlg .bd{overflow:auto;padding:8px 14px;display:grid;grid-template-columns:1fr 220px auto;gap:4px 8px;align-items:center}
.sh-pv-dlg .bd .fn{font-family:ui-monospace,Consolas,monospace;font-size:12px;word-break:break-all}
.sh-pv-dlg .bd .used{color:var(--sh-brass);font-size:11px}
.sh-pv-dlg input{background:var(--comfy-input-bg,#151515);color:inherit;border:1px solid var(--border-color,#444);border-radius:4px;padding:4px 6px}
.sh-pv-dlg button{padding:5px 12px;border:1px solid var(--border-color,#444);background:var(--comfy-input-bg,#151515);color:inherit;border-radius:4px;cursor:pointer}
.sh-pv-dlg button.pri{border-color:#c9a227;color:#c9a227}
`;

function injectCss() {
  if (document.getElementById("sh-pv-css")) return;
  const s = document.createElement("style");
  s.id = "sh-pv-css";
  s.textContent = CSS;
  document.head.appendChild(s);
}

const el = (tag, props = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e[k] = v;
  }
  for (const k of kids) if (k !== null && k !== undefined && k !== "") e.append(k);
  return e;
};

function hideWidget(w) {
  if (!w) return;
  w.hidden = true;
  w.computeSize = () => [0, -4];
  w.computedHeight = 0;
  if (w.element) w.element.style.display = "none";
}

const fmtVal = (v) => (v === null || v === undefined || v === "") ? "" : String(v);
const baseName = (f) => String(f).split(/[\\/]/).pop();

/* ------------------------------------------------------- shortnames dialog */

async function openShortnames(files, onSaved) {
  let table = {};
  try {
    const r = await (await api.fetchApi(`${ROUTE}/shortnames`)).json();
    if (r.ok) table = r.shortnames || {};
  } catch { /* empty table */ }
  const used = new Set(files.map(baseName));
  const keys = [...new Set([...used, ...Object.keys(table)])].sort((a, b) => a.localeCompare(b));
  const inputs = new Map();
  const body = el("div", { class: "bd" });
  body.append(el("b", { textContent: "File" }), el("b", { textContent: "Shortname" }), el("span"));
  for (const k of keys) {
    const inp = el("input", { type: "text", value: table[k] || "", placeholder: "(file name)" });
    inp.addEventListener("keydown", (e) => e.stopPropagation());
    inputs.set(k, inp);
    body.append(el("span", { class: "fn", textContent: k }), inp,
      el("span", { class: "used", textContent: used.has(k) ? "in this workflow" : "" }));
  }
  if (!keys.length) body.append(el("span", { textContent: "No model, LoRA, CLIP or VAE files found in this workflow." }));
  const addName = el("input", { type: "text", placeholder: "file name, e.g. my_lora_v2.safetensors", style: "flex:1" });
  addName.addEventListener("keydown", (e) => e.stopPropagation());
  const dlg = el("div", { class: "sh-pv-dlg" });
  const close = () => dlg.remove();
  const save = async () => {
    const out = { ...table };
    for (const [k, inp] of inputs) { const v = inp.value.trim(); if (v) out[k] = v; else delete out[k]; }
    try {
      const r = await (await api.fetchApi(`${ROUTE}/shortnames`, { method: "POST", body: JSON.stringify({ shortnames: out }) })).json();
      if (!r.ok) throw new Error(r.error);
      close(); onSaved?.();
    } catch (e) { alert(`Could not save shortnames: ${e.message}`); }
  };
  const add = () => {
    const k = baseName(addName.value.trim());
    if (!k || inputs.has(k)) return;
    const inp = el("input", { type: "text", placeholder: "(file name)" });
    inp.addEventListener("keydown", (e) => e.stopPropagation());
    inputs.set(k, inp);
    body.append(el("span", { class: "fn", textContent: k }), inp, el("span"));
    addName.value = ""; inp.focus();
  };
  dlg.append(el("div", { class: "box" },
    el("div", { class: "hd" }, el("b", { textContent: "Shortnames" }),
      el("span", { style: "opacity:.65;font-size:12px", textContent: "Recorded instead of the file name. Shared by every workflow. Subfolders are always stripped." })),
    body,
    el("div", { class: "ft" }, addName, el("button", { textContent: "Add", onclick: add }),
      el("span", { style: "flex:1" }),
      el("button", { textContent: "Cancel", onclick: close }),
      el("button", { class: "pri", textContent: "Save", onclick: save }))));
  dlg.addEventListener("pointerdown", (e) => { if (e.target === dlg) close(); });
  document.body.appendChild(dlg);
}

/* --------------------------------------------------------------- node UI */

function setup(node) {
  injectCss();
  const W = (n) => node.widgets?.find((w) => w.name === n);
  const wOvr = W("overrides"), wSel = W("selection");
  hideWidget(wOvr); hideWidget(wSel);

  const st = {
    ovr: {}, keys: new Set(), res: null, collapsed: new Set(), executed: null,
    lastScan: 0, busy: false, again: false, showJson: false,
  };
  const loadState = () => {
    try { st.ovr = JSON.parse(wOvr?.value || "{}") || {}; } catch { st.ovr = {}; }
    try { st.keys = new Set(JSON.parse(wSel?.value || "{}").keys || []); } catch { st.keys = new Set(); }
  };
  const saveOvr = () => { if (wOvr) wOvr.value = JSON.stringify(st.ovr); app.graph?.change?.(); };
  const saveSel = () => { if (wSel) wSel.value = JSON.stringify({ v: 1, keys: [...st.keys] }); app.graph?.change?.(); };

  /* --- DOM --- */
  const status = el("span", { class: "sh-pv-status" });
  const samplerSel = el("select", { title: "Sampler to read the card from", style: "display:none;max-width:180px" });
  samplerSel.addEventListener("change", () => { st.ovr.sampler = samplerSel.value; saveOvr(); refresh(); });
  const fieldsBox = el("div", { class: "sh-pv-fields" });
  const setBox = el("div", { class: "sh-pv-set" });
  const notesBox = el("div", { class: "sh-pv-notes" });
  const filter = el("input", { type: "text", placeholder: "Filter settings…", style: "flex:1;min-width:80px" });
  const onlyTicked = el("input", { type: "checkbox" });
  const list = el("div", { class: "sh-pv-list" });
  const out = el("textarea", { class: "sh-pv-out", readOnly: true, spellcheck: false, style: "display:none" });
  const outLabel = el("span", { style: "opacity:.7;font-size:11px" });
  const btnJson = el("button", { textContent: "Show embedded JSON", onclick: () => { st.showJson = !st.showJson; renderOut(); } });
  const btnCopy = el("button", { textContent: "Copy", onclick: () => copyOut() });

  const scroll = el("div", { class: "sh-pv-scroll" },
    el("div", { class: "sh-pv-h", textContent: "Card" }), fieldsBox, notesBox,
    el("div", { class: "sh-pv-h", textContent: "Settings (recorded automatically)" }), setBox,
    el("div", { class: "sh-pv-h", textContent: "Extra settings for the metadata section" }),
    el("div", { class: "sh-pv-bar" }, filter,
      el("button", { textContent: "All", title: "Tick everything shown", onclick: () => bulk(true) }),
      el("button", { textContent: "None", title: "Untick everything shown", onclick: () => bulk(false) }),
      el("button", { textContent: "Fold", onclick: () => foldAll() }),
      el("label", { title: "Show only ticked settings" }, onlyTicked, "Ticked")),
    list,
    el("div", { class: "sh-pv-bar" }, btnJson, outLabel, el("span", { style: "margin-left:auto" }), btnCopy),
    out);

  const root = el("div", { class: "sh-pv" },
    el("div", { class: "sh-pv-bar" },
      el("button", { class: "pri", textContent: "Refresh", title: "Re-read the workflow", onclick: () => refresh() }),
      el("button", { textContent: "Shortnames…", title: "Short names recorded instead of long model / LoRA file names",
        onclick: () => openShortnames(st.res?.files || [], refresh) }),
      samplerSel, status),
    scroll);

  for (const ev of ["wheel", "pointerdown", "mousedown"]) scroll.addEventListener(ev, (e) => e.stopPropagation(), { passive: true });
  root.addEventListener("keydown", (e) => e.stopPropagation());
  filter.addEventListener("input", () => renderList());
  onlyTicked.addEventListener("change", () => renderList());
  root.addEventListener("pointerenter", () => { if (Date.now() - st.lastScan > 1500) refresh(true); });

  // Only a minimum height: ComfyUI hands the panel the node's spare height, the way its own
  // multiline text boxes grow, so dragging the node taller gives the extras list more room.
  // Never derive the panel's height from node.size — that fed back into itself (v1.1.0).
  const PANEL_MIN = 720;
  node.addDOMWidget("pv_panel", "sh_pv_panel", root, {
    serialize: false, hideOnZoom: false, getMinHeight: () => PANEL_MIN });

  const setStatus = (m, err = false) => { status.textContent = m; status.title = m; status.classList.toggle("err", err); };

  /* --- data --- */
  function widgetFields() {
    const g = (n) => W(n)?.value;
    return { category: g("category") ?? "", tags: g("tags") ?? "", label: g("label") ?? "",
             notes: g("notes") ?? "", protected: g("protected") === true,
             author: g("author") ?? "", author_url: g("author_url") ?? "", source_url: g("source_url") ?? "" };
  }

  async function refresh(quiet = false) {
    if (st.busy) { st.again = true; return; }
    st.busy = true;
    try {
      const p = await app.graphToPrompt();
      const r = await (await api.fetchApi(`${ROUTE}/resolve`, {
        method: "POST",
        body: JSON.stringify({ prompt: p.output || {}, card_id: String(node.id), fields: widgetFields(),
                               overrides: st.ovr, selection: [...st.keys] }),
      })).json();
      if (!r.ok) throw new Error(r.error);
      st.res = r;
      st.lastScan = Date.now();
      if (!quiet) st.executed = null;
      setStatus(r.sampler ? `Reading from ${r.samplers.find((s) => s.id === r.sampler)?.title || r.sampler}` : "No sampler found");
    } catch (e) {
      setStatus(`Preview failed: ${e.message}`, true);
    } finally {
      st.busy = false;
    }
    renderAll();
    if (st.again) { st.again = false; refresh(true); }
  }

  /* --- rendering --- */
  function renderFields() {
    fieldsBox.replaceChildren();
    const r = st.res;
    for (const [f, label, multi] of FIELDS) {
      const o = st.ovr[f] || {};
      const src = r?.sources?.[f] || "";
      const resolved = r ? r.card[CARD_KEY[f]] : "";
      const cb = el("input", { type: "checkbox", checked: !!o.on });
      cb.addEventListener("change", () => {
        st.ovr[f] = cb.checked ? { on: true, value: o.value || fmtVal(resolved) } : { on: false, value: o.value || "" };
        saveOvr(); renderFields(); refresh(true);
      });
      let valEl;
      if (o.on) {
        valEl = multi ? el("textarea", { value: o.value ?? "", spellcheck: false })
                      : el("input", { type: "text", value: o.value ?? "",
                          placeholder: f === "ratio" ? "e.g. 16:9" : "" });
        valEl.addEventListener("input", () => { st.ovr[f] = { on: true, value: valEl.value }; saveOvr(); });
        valEl.addEventListener("change", () => refresh(true));
        for (const ev of ["wheel", "pointerdown"]) valEl.addEventListener(ev, (e) => e.stopPropagation(), { passive: true });
      } else {
        const t = fmtVal(resolved);
        valEl = el("div", { class: "val" + (t ? "" : " empty"), textContent: t || "—", title: t });
      }
      const warn = /not found|wire its|known when/.test(src);
      fieldsBox.append(
        el("span", { class: "f", textContent: label }),
        el("div", { class: "v" }, valEl, el("div", { class: "src" + (o.on ? " ovr" : warn ? " warn" : ""), textContent: o.on ? "override (typed here)" : src })),
        el("label", { class: "o", title: "Use what you type instead of the wired or traced value" }, cb, "Override"));
    }
    notesBox.textContent = (r?.notes || []).join(" ");
    // sampler choice
    const ss = r?.samplers || [];
    samplerSel.style.display = ss.length > 1 ? "" : "none";
    samplerSel.replaceChildren(...ss.map((s) => el("option", { value: s.id, textContent: s.title, selected: s.id === r.sampler })));
  }

  function renderSettings() {
    setBox.replaceChildren();
    const m = st.res?.meta || {};
    const row = (k, v) => { if (v !== undefined && v !== "" && v !== null) setBox.append(el("span", { class: "k", textContent: k }), el("span", { class: "lv", textContent: v })); };
    row("Model", m.model);
    row("CLIP", (m.clip || []).join(", "));
    row("VAE", m.vae);
    for (const [i, l] of (m.loras || []).entries())
      row(i ? "" : "LoRAs", `${l.name}  ·  ${l.model}${l.clip !== undefined ? " / " + l.clip : ""}`);
    if (st.res && !(m.loras || []).length) row("LoRAs", "none in use");
    const samp = [m.sampler, m.scheduler].filter(Boolean).join(" · ");
    row("Sampler", samp);
    const nums = [m.steps !== undefined ? `steps ${m.steps}` : "", m.cfg !== undefined ? `cfg ${m.cfg}` : "",
                  m.denoise !== undefined ? `denoise ${m.denoise}` : ""].filter(Boolean).join(" · ");
    row("", nums);
  }

  function visibleEntries() {
    const f = filter.value.trim().toLowerCase();
    return (st.res?.entries || []).filter((e) =>
      (!onlyTicked.checked || st.keys.has(e.key)) &&
      (!f || e.title.toLowerCase().includes(f) || e.cls.toLowerCase().includes(f) || e.name.toLowerCase().includes(f)));
  }

  function renderList() {
    const top = list.scrollTop;
    list.replaceChildren();
    const auto = new Set(st.res?.auto_keys || []);
    const groups = new Map();
    for (const e of visibleEntries()) {
      if (!groups.has(e.id)) groups.set(e.id, { id: e.id, title: e.title, cls: e.cls, items: [] });
      groups.get(e.id).items.push(e);
    }
    if (!groups.size) { list.append(el("div", { style: "padding:10px;opacity:.6", textContent: st.res ? "No settings match." : "Reading workflow…" })); return; }
    for (const g of groups.values()) {
      const pick = g.items.filter((e) => !auto.has(e.key));
      const ticked = pick.filter((e) => st.keys.has(e.key)).length;
      const cb = el("input", { type: "checkbox", disabled: !pick.length, checked: pick.length > 0 && ticked === pick.length,
                               indeterminate: ticked > 0 && ticked < pick.length });
      cb.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const on = ticked < pick.length;
        for (const e of pick) on ? st.keys.add(e.key) : st.keys.delete(e.key);
        changed();
      });
      const folded = st.collapsed.has(g.id);
      const head = el("div", { class: "sh-pv-grp", title: `Node ${g.id} · ${g.cls}` },
        el("span", { textContent: folded ? "▸" : "▾" }), cb, el("span", { class: "t", textContent: g.title }),
        g.title !== g.cls ? el("span", { class: "c", textContent: g.cls }) : "",
        el("span", { class: "n", textContent: `${ticked}/${pick.length}` }));
      head.addEventListener("click", () => { folded ? st.collapsed.delete(g.id) : st.collapsed.add(g.id); renderList(); });
      list.append(head);
      if (folded) continue;
      for (const e of g.items) {
        const isAuto = auto.has(e.key);
        const rcb = el("input", { type: "checkbox", checked: isAuto || st.keys.has(e.key), disabled: isAuto });
        rcb.addEventListener("change", () => { rcb.checked ? st.keys.add(e.key) : st.keys.delete(e.key); changed(); });
        list.append(el("label", { class: "sh-pv-row" + (isAuto ? " isauto" : ""), title: e.value.slice(0, 600) },
          rcb, el("span", { class: "k", textContent: e.name }),
          el("span", { class: "lv", textContent: e.value.replace(/\s+/g, " ") }),
          isAuto ? el("span", { class: "auto", textContent: "recorded automatically" })
                 : e.linked ? el("span", { class: "auto", textContent: `🔗 ${e.linked.from}` }) : ""));
      }
    }
    list.scrollTop = top;
  }

  function renderOut() {
    out.style.display = st.showJson ? "" : "none";
    btnJson.textContent = st.showJson ? "Hide embedded JSON" : "Show embedded JSON";
    if (st.executed) { out.value = st.executed; outLabel.textContent = "As embedded at the last run"; }
    else { out.value = st.res?.chunk || ""; outLabel.textContent = st.showJson ? "Preview — wired values fill in when it runs" : ""; }
  }

  function renderAll() { renderFields(); renderSettings(); renderList(); renderOut(); }
  function changed() { saveSel(); renderList(); refresh(true); }
  function bulk(on) {
    const auto = new Set(st.res?.auto_keys || []);
    for (const e of visibleEntries()) if (!auto.has(e.key)) on ? st.keys.add(e.key) : st.keys.delete(e.key);
    changed();
  }
  function foldAll() {
    const ids = [...new Set((st.res?.entries || []).map((e) => e.id))];
    if (ids.every((i) => st.collapsed.has(i))) st.collapsed.clear(); else ids.forEach((i) => st.collapsed.add(i));
    renderList();
  }
  async function copyOut() {
    const t = st.executed || st.res?.chunk || "";
    if (!t) return;
    try { await navigator.clipboard.writeText(t); } catch { out.style.display = ""; out.select(); document.execCommand("copy"); }
    const o = btnCopy.textContent; btnCopy.textContent = "Copied ✓"; setTimeout(() => (btnCopy.textContent = o), 1200);
  }

  // Card widgets refresh the preview when edited.
  for (const n of ["category", "tags", "label", "notes", "protected", "author", "author_url", "source_url"]) {
    const w = W(n);
    if (!w) continue;
    const orig = w.callback;
    w.callback = function () { const r = orig?.apply(this, arguments); setTimeout(() => refresh(true), 0); return r; };
  }

  node.__shpv = {
    afterConfigure() { loadState(); setTimeout(() => refresh(), 300); },
    showExecuted(text) {
      try {
        const d = JSON.parse(text);
        st.executed = JSON.stringify(d.payload, null, 2);
        if (d.notes?.length) notesBox.textContent = d.notes.join(" ");
      } catch { st.executed = text; }
      renderOut();
    },
  };

  loadState();
  // Size once, from the widgets' own heights. A reopened workflow keeps the size it was
  // saved with, unless that is a runaway height left by v1.1.0's sizing bug.
  setTimeout(() => {
    const need = node.computeSize?.() || [520, 900];
    const h = node.size?.[1] || 0;
    const keep = node.__shpvConfigured && h >= need[1] && h <= need[1] + 1500;
    if (!keep) node.setSize([Math.max(node.size?.[0] || 0, 520, need[0]), need[1]]);
    node.setDirtyCanvas?.(true, true);
  }, 50);
  setTimeout(() => { if (!node.__shpvConfigured) refresh(); }, 300);
}

app.registerExtension({
  name: "SmallerHammer.PromptVaultCard",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;
    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      setup(this);
      return r;
    };
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfigure?.apply(this, arguments);
      this.__shpvConfigured = true;
      this.__shpv?.afterConfigure();
      return r;
    };
    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      this.__shpv?.showExecuted(message?.text?.[0] ?? "");
    };
  },
});
