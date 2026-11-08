"""
Prompt Vault Card — resolver core. A Smaller Hammer node for ComfyUI.

Works out, from an API-format prompt (the graph ComfyUI actually ran), the
fields of a Prompt Vault card and its generation settings:

  * positive / negative prompt  — traced from the sampler's conditioning inputs
  * seed, width, height, ratio  — sampler seed, latent size, Olm Resolution Picker
  * model, CLIP, VAE, LoRAs      — following the sampler's MODEL chain, so only
                                   LoRAs actually in use are recorded (strength 0 is
                                   treated as not in use)
  * extras                       — any other ticked setting

Priority for every card field: Override (typed on the node) > wired input >
traced from the workflow. Nothing here imports ComfyUI, so it can be tested
on its own.

Copyright (c) 2026 Smaller Hammer - MIT Licence
"""

import json
import math
import re
from datetime import datetime, timezone

PV_CHUNK_KEY = "promptvault"
PV_FORMAT = 1
CARD_CLASS = "SH_PromptVaultCard"
NODE_VERSION = "1.2.0"
MAX_DEPTH = 60

# Inputs that describe the Card node itself, never listed as extras.
SKIP_CLASSES = {CARD_CLASS, "SH_PromptVaultSave", "SH_WorkflowCapture"}

MODEL_EXT = re.compile(r"\.(safetensors|ckpt|pt|pth|bin|gguf|sft)$", re.I)
OLM_CLASS = "OlmResolutionPicker"
PROMPT_LIST_CLASS = "SmallerHammerPromptListEncode"
OLM_LABEL = re.compile(r"^\s*(\d+)\s*[x×]\s*(\d+)(?:.*?\((\d+)\s*:\s*(\d+)\))?")

CARD_FIELDS = ("positive", "negative", "seed", "width", "height", "ratio")
RATIO_MAX_TERM = 21   # an exact ratio counts as "standard" only with small terms


# ---------------------------------------------------------------- basics --

def is_link(v):
    return (isinstance(v, list) and len(v) == 2
            and isinstance(v[0], (str, int)) and not isinstance(v[0], bool)
            and isinstance(v[1], int) and not isinstance(v[1], bool))


def id_sort_key(node_id):
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in str(node_id).split(":")]


def norm_number(v):
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
        if v.is_integer():
            return int(v)
    return v


def norm_json(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, float):
        return norm_number(v)
    if isinstance(v, list):
        return [norm_json(x) for x in v]
    if isinstance(v, dict):
        return {str(k): norm_json(x) for k, x in v.items()}
    return v


def to_text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(norm_number(v))
    if isinstance(v, str):
        return v
    return json.dumps(norm_json(v), separators=(",", ":"), ensure_ascii=False)


def titles_for(prompt):
    raw, counts = {}, {}
    for nid, n in prompt.items():
        t = ((n.get("_meta") or {}).get("title") or n.get("class_type") or f"Node {nid}").strip()
        raw[nid] = t
        counts[t] = counts.get(t, 0) + 1
    return {nid: (f"{t} #{nid}" if counts[t] > 1 else t) for nid, t in raw.items()}


# ------------------------------------------------------------- shortnames --

def base_name(filename):
    """Strip any subfolder: 'sliders\\skin.safetensors' -> 'skin.safetensors'."""
    return re.split(r"[\\/]", str(filename))[-1]


def short_name(filename, table):
    """Shortname if one is set for this file (matched on its base name), else the base name."""
    if not filename:
        return ""
    b = base_name(filename)
    for key in (b, MODEL_EXT.sub("", b)):
        v = (table or {}).get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return b


def clean_shortnames(data):
    out = {}
    if isinstance(data, dict):
        for k, v in data.items():
            k, v = base_name(str(k)).strip(), str(v or "").strip()
            if k and v:
                out[k] = v[:80]
    return out


# ----------------------------------------------------------------- ratio --

def _gcd(a, b):
    while b:
        a, b = b, a % b
    return a


def standard_ratio(w, h):
    """Exact reduced ratio only when it is a 'standard' one (both terms <= 21).
    1024x1536 -> 2:3, but 1088x1920 -> '' (17:30 is too literal)."""
    try:
        w, h = int(w), int(h)
    except (TypeError, ValueError):
        return ""
    if w <= 0 or h <= 0:
        return ""
    g = _gcd(w, h)
    a, b = w // g, h // g
    return f"{a}:{b}" if a <= RATIO_MAX_TERM and b <= RATIO_MAX_TERM else ""


def olm_size(inputs):
    """(width, height, ratio) from an Olm Resolution Picker's widgets, or None."""
    label = str(inputs.get("resolution", ""))
    m = OLM_LABEL.match(label)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        ratio = f"{m.group(3)}:{m.group(4)}" if m.group(3) else ""
    else:
        cw, ch = inputs.get("custom_width"), inputs.get("custom_height")
        if not isinstance(cw, int) or not isinstance(ch, int):
            return None
        w, h, ratio = cw, ch, ""
    if inputs.get("swap_dimensions") is True:
        w, h = h, w
        if ratio:
            a, b = ratio.split(":")
            ratio = f"{b}:{a}"
    return w, h, ratio


# ----------------------------------------------------------- resolution --

class Resolver:
    """Reads values out of one API-format prompt."""

    def __init__(self, prompt):
        self.p = prompt or {}
        self.titles = titles_for(self.p)
        self.notes = []

    def node(self, nid):
        return self.p.get(str(nid))

    def title(self, nid):
        return self.titles.get(str(nid), str(nid))

    def value(self, v, depth=0):
        """A literal value, or the value behind a link where it can be found.
        Returns (value, source_title or None, resolved: bool)."""
        if not is_link(v):
            return v, None, True
        sid, slot = str(v[0]), v[1]
        src = self.node(sid)
        if src is None or depth > MAX_DEPTH:
            return None, f"Node {sid}", False
        title = self.title(sid)
        ins = src.get("inputs") or {}
        cls = src.get("class_type", "")
        if cls == OLM_CLASS:
            s = olm_size(ins)
            if s and slot in (0, 1):
                return s[slot], title, True
            return None, title, False
        if cls == PROMPT_LIST_CLASS:
            return None, title, False          # read from file at run time
        if "value" in ins:
            cand = ins["value"]
        elif len(ins) == 1:
            cand = next(iter(ins.values()))
        else:
            return None, title, False
        if is_link(cand):
            val, _, ok = self.value(cand, depth + 1)
            return val, title, ok
        return cand, title, True

    # --- samplers ---
    def samplers(self):
        out = []
        for nid in sorted(self.p, key=id_sort_key):
            ins = self.p[nid].get("inputs") or {}
            if "positive" in ins and "negative" in ins and ("model" in ins or "guider" in ins):
                out.append(nid)
        return out

    def pick_sampler(self, wanted=None):
        ids = self.samplers()
        if wanted and str(wanted) in ids:
            return str(wanted), ids
        return (ids[0] if ids else None), ids

    # --- prompts ---
    def trace_text(self, link):
        """Follow a CONDITIONING link back to the text that made it.
        Returns (text or None, how) where how is 'traced', 'zeroed',
        'prompt-list' or 'unknown'."""
        seen = set()
        cur = link
        for _ in range(MAX_DEPTH):
            if not is_link(cur):
                return None, "unknown"
            nid = str(cur[0])
            if nid in seen:
                return None, "unknown"
            seen.add(nid)
            n = self.node(nid)
            if n is None:
                return None, "unknown"
            cls = n.get("class_type", "")
            ins = n.get("inputs") or {}
            if cls == PROMPT_LIST_CLASS:
                return None, "prompt-list"
            if "ZeroOut" in cls:
                return "", "zeroed"
            for key in ("text", "text_g", "prompt", "positive_prompt"):
                if key in ins:
                    val, _, ok = self.value(ins[key])
                    if ok and isinstance(val, str):
                        return val, "traced"
                    return None, "unknown"
            nxt = None
            for key in ("conditioning", "conditioning_1", "conditioning_to", "positive", "cond"):
                if is_link(ins.get(key)):
                    nxt = ins[key]
                    break
            if nxt is None:
                links = [v for v in ins.values() if is_link(v)]
                if len(links) == 1:
                    nxt = links[0]
            cur = nxt
        return None, "unknown"

    # --- model chain ---
    def follow_switch(self, ins):
        sw = ins.get("switch", ins.get("boolean", ins.get("condition")))
        if isinstance(sw, bool):
            a = ins.get("on_true", ins.get("true"))
            b = ins.get("on_false", ins.get("false"))
            return a if sw else b
        return None

    def model_chain(self, link):
        """Walk a MODEL link down to the loader. Returns (model_file, [lora dicts]),
        LoRAs listed from the base model up, as they are applied."""
        loras, model, seen, cur = [], None, set(), link
        for _ in range(MAX_DEPTH):
            if not is_link(cur):
                break
            nid = str(cur[0])
            if nid in seen:
                break
            seen.add(nid)
            n = self.node(nid)
            if n is None:
                break
            ins = n.get("inputs") or {}
            for key in ("unet_name", "ckpt_name", "model_name", "gguf_name"):
                if isinstance(ins.get(key), str):
                    model = ins[key]
                    break
            if model:
                break
            if "lora_name" in ins:
                sm, _, _ = self.value(ins.get("strength_model", ins.get("strength")))
                sc = ins.get("strength_clip")
                sc = self.value(sc)[0] if sc is not None else None
                d = {"file": self.value(ins["lora_name"])[0], "model": norm_number(sm)}
                if sc is not None:
                    d["clip"] = norm_number(sc)
                # A LoRA at strength 0 (model, and clip when it has one) has no effect: leave it out.
                off = (d["model"] == 0) and d.get("clip", 0) == 0
                if d["file"] and not off:
                    loras.append(d)
            nxt = ins.get("model")
            if not is_link(nxt):
                nxt = self.follow_switch(ins)
            if not is_link(nxt):
                links = [v for v in ins.values() if is_link(v)]
                nxt = links[0] if len(links) == 1 else None
            cur = nxt
        loras.reverse()
        return model, loras

    def clip_files(self, encode_link):
        """CLIP file name(s) behind the text encoder that produced a conditioning."""
        seen, cur = set(), encode_link
        # step to the node that has a 'clip' input
        for _ in range(MAX_DEPTH):
            if not is_link(cur) or str(cur[0]) in seen:
                return []
            seen.add(str(cur[0]))
            n = self.node(cur[0])
            if n is None:
                return []
            ins = n.get("inputs") or {}
            if is_link(ins.get("clip")):
                cur = ins["clip"]
                break
            links = [v for v in ins.values() if is_link(v)]
            cur = links[0] if len(links) == 1 else None
        for _ in range(MAX_DEPTH):
            if not is_link(cur):
                return []
            n = self.node(cur[0])
            if n is None:
                return []
            ins = n.get("inputs") or {}
            names = [ins[k] for k in sorted(ins) if re.fullmatch(r"clip_name\d*", k) and isinstance(ins[k], str)]
            if names:
                return names
            if isinstance(ins.get("ckpt_name"), str):
                return []        # CLIP comes from the checkpoint
            nxt = ins.get("clip")
            if not is_link(nxt):
                nxt = self.follow_switch(ins)
            cur = nxt
        return []

    def vae_file(self):
        for nid in sorted(self.p, key=id_sort_key):
            n = self.p[nid]
            if n.get("class_type") in ("VAEDecode", "VAEDecodeTiled"):
                cur = (n.get("inputs") or {}).get("vae")
                for _ in range(MAX_DEPTH):
                    if not is_link(cur):
                        break
                    m = self.node(cur[0])
                    if m is None:
                        break
                    ins = m.get("inputs") or {}
                    if isinstance(ins.get("vae_name"), str):
                        return ins["vae_name"]
                    if isinstance(ins.get("ckpt_name"), str):
                        return ""
                    cur = ins.get("vae") if is_link(ins.get("vae")) else self.follow_switch(ins)
        return ""

    def latent_size(self, link):
        """(width, height, ratio, how) from the sampler's latent input."""
        cur, seen = link, set()
        for _ in range(MAX_DEPTH):
            if not is_link(cur) or str(cur[0]) in seen:
                return None
            seen.add(str(cur[0]))
            n = self.node(cur[0])
            if n is None:
                return None
            ins = n.get("inputs") or {}
            if "width" in ins and "height" in ins:
                ratio = ""
                for k in ("width", "height"):
                    v = ins[k]
                    if is_link(v):
                        src = self.node(v[0])
                        if src and src.get("class_type") == OLM_CLASS:
                            s = olm_size(src.get("inputs") or {})
                            if s:
                                ratio = s[2]
                w, _, okw = self.value(ins["width"])
                h, _, okh = self.value(ins["height"])
                if okw and okh and isinstance(w, int) and isinstance(h, int):
                    return w, h, ratio
                return None
            for k in ("samples", "latent", "latent_image", "pixels"):
                if is_link(ins.get(k)):
                    cur = ins[k]
                    break
            else:
                return None
        return None


# ------------------------------------------------------------ card build --

def _split_tags(s):
    out, seen = [], set()
    for t in re.split(r"[,\n]", s or ""):
        t = t.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:50]


def list_entries(prompt, card_id=None):
    """One entry per node input, for the extras tick list."""
    r = Resolver(prompt)
    out = []
    for nid in sorted(r.p, key=id_sort_key):
        n = r.p[nid]
        if n.get("class_type") in SKIP_CLASSES or str(nid) == str(card_id):
            continue
        for name, v in (n.get("inputs") or {}).items():
            e = {"key": f"{nid}::{name}", "id": str(nid), "title": r.title(nid),
                 "cls": n.get("class_type", ""), "name": name, "linked": None}
            if is_link(v):
                val, frm, ok = r.value(v)
                e["value"] = to_text(val) if ok else f"<{frm} · output {v[1]}>"
                e["linked"] = {"from": frm, "resolved": ok}
            else:
                e["value"] = to_text(v)
            out.append(e)
    return out


def build_card(prompt, card_id=None, fields=None, wired=None, overrides=None,
               selection=None, shortnames=None, preview=False):
    """
    Build {card, meta, sources, notes, samplers, auto_keys}.

    fields     the Card node's own widgets: category, tags, label, notes, protected
    wired      values arriving on the node's optional inputs (None = not wired)
    overrides  {"positive": {"on": bool, "value": str}, ..., "sampler": id}
    selection  set of "nodeId::input" keys ticked as extras
    preview    True when called from the editor (wired inputs are links then)
    """
    r = Resolver(prompt)
    fields = fields or {}
    wired = wired or {}
    overrides = overrides or {}
    selection = set(selection or ())
    sn = shortnames or {}
    sources, notes, auto_keys = {}, [], set()

    sid, sids = r.pick_sampler(overrides.get("sampler"))
    s_in = (r.node(sid) or {}).get("inputs") or {} if sid else {}
    if sid:
        for k in ("positive", "negative", "seed", "noise_seed", "steps", "cfg", "sampler_name",
                  "scheduler", "denoise", "model", "latent_image"):
            if k in s_in:
                auto_keys.add(f"{sid}::{k}")
    elif not preview:
        notes.append("No sampler found in this workflow.")

    # --- traced values ---
    traced = {}
    if sid:
        pos, how = r.trace_text(s_in.get("positive"))
        traced["positive"] = (pos, how)
        neg, nhow = r.trace_text(s_in.get("negative"))
        traced["negative"] = (neg, nhow)
        for lk, kind in ((s_in.get("positive"), "positive"), (s_in.get("negative"), "negative")):
            cur = lk
            for _ in range(MAX_DEPTH):
                if not is_link(cur):
                    break
                n = r.node(cur[0]) or {}
                ins = n.get("inputs") or {}
                hit = next((k for k in ("text", "text_g", "prompt", "positive_prompt") if k in ins), None)
                if hit:
                    auto_keys.add(f"{cur[0]}::{hit}")
                    break
                cur = next((ins[k] for k in ("conditioning", "conditioning_1", "conditioning_to", "positive", "cond")
                            if is_link(ins.get(k))), None)
        seed_v = s_in.get("seed", s_in.get("noise_seed"))
        sv, _, ok = r.value(seed_v)
        traced["seed"] = (to_text(sv) if ok and sv is not None else None, "traced")
        if is_link(seed_v):
            auto_keys.add(f"{seed_v[0]}::seed")
        size = r.latent_size(s_in.get("latent_image"))
        if size:
            traced["width"] = (size[0], "traced")
            traced["height"] = (size[1], "traced")
            traced["ratio"] = (size[2] or standard_ratio(size[0], size[1]) or None,
                               "olm" if size[2] else "standard")
    # Olm picker anywhere (also covers a picker wired straight into the node)
    for nid, n in r.p.items():
        if n.get("class_type") == OLM_CLASS:
            auto_keys.add(f"{nid}::resolution")

    # --- wired values (preview: links -> best effort) ---
    wired_vals = {}
    card_node = r.node(card_id) if card_id is not None else None
    card_ins = (card_node or {}).get("inputs") or {}
    for f in CARD_FIELDS:
        if preview:
            v = card_ins.get(f)
            if is_link(v):
                val, frm, ok = r.value(v)
                src = r.node(v[0]) or {}
                if src.get("class_type") == PROMPT_LIST_CLASS:
                    wired_vals[f] = (None, f"wired from {frm} — known when it runs")
                elif ok:
                    wired_vals[f] = (val, f"wired from {frm}")
                else:
                    wired_vals[f] = (None, f"wired from {frm} — known when it runs")
        elif wired.get(f) is not None:
            wired_vals[f] = (wired[f], "wired")

    # --- combine: override > wired > traced ---
    card = {}
    for f in CARD_FIELDS:
        ov = overrides.get(f) or {}
        if isinstance(ov, dict) and ov.get("on"):
            card[f], sources[f] = ov.get("value", ""), "override"
        elif f in wired_vals:
            card[f], sources[f] = wired_vals[f][0], wired_vals[f][1]
        elif f in traced and traced[f][0] is not None:
            how = traced[f][1]
            card[f] = traced[f][0]
            sources[f] = {"traced": "from workflow", "zeroed": "zeroed out (empty)",
                          "olm": "from Olm Resolution Picker", "standard": "exact standard ratio"}.get(how, how)
        else:
            card[f] = None
            how = traced.get(f, (None, ""))[1]
            if how == "prompt-list":
                sources[f] = "Prompt List — wire its 'prompt' output here"
                notes.append(f"The {f} prompt comes from Prompt List Encode: wire its 'prompt' output into '{f}'.")
            elif f == "ratio":
                sources[f] = "not found — fill in with Override"
            else:
                sources[f] = "not found"

    # tidy types
    if wired_vals.get("ratio") and isinstance(card.get("ratio"), str):
        card["ratio"] = card["ratio"].strip()
    for f in ("width", "height"):
        v = card.get(f)
        if isinstance(v, str):
            v = v.strip()
            card[f] = int(v) if v.isdigit() else None
        elif isinstance(v, float) and v.is_integer():
            card[f] = int(v)
        elif not isinstance(v, int) or isinstance(v, bool):
            card[f] = None
    for f in ("positive", "negative", "seed", "ratio"):
        if card.get(f) is not None and not isinstance(card[f], str):
            card[f] = to_text(card[f])

    # --- settings ---
    meta = {}
    if sid:
        model, loras = r.model_chain(s_in.get("model"))
        if model:
            meta["model"] = short_name(model, sn)
        clips = r.clip_files(s_in.get("positive"))
        if clips:
            meta["clip"] = [short_name(c, sn) for c in clips]
        vae = r.vae_file()
        if vae:
            meta["vae"] = short_name(vae, sn)
        if loras:
            meta["loras"] = [{"name": short_name(l["file"], sn),
                              **{k: v for k, v in l.items() if k != "file"}} for l in loras]
        for src_key, dst in (("sampler_name", "sampler"), ("scheduler", "scheduler"),
                             ("steps", "steps"), ("cfg", "cfg"), ("denoise", "denoise")):
            if src_key in s_in:
                v, _, ok = r.value(s_in[src_key])
                if ok and v is not None:
                    meta[dst] = norm_number(v)
        # mark loader/lora inputs as auto
        for nid, n in r.p.items():
            ins = n.get("inputs") or {}
            for k in ins:
                if (k in ("unet_name", "ckpt_name", "vae_name") or re.fullmatch(r"clip_name\d*", k)
                        or ("lora_name" in ins and k in ("lora_name", "strength_model", "strength_clip", "strength"))):
                    auto_keys.add(f"{nid}::{k}")

    extras = []
    if selection:
        for e in list_entries(prompt, card_id):
            if e["key"] in selection and e["key"] not in auto_keys:
                val = e["value"]
                if MODEL_EXT.search(val or ""):
                    val = short_name(val, sn)
                extras.append({"node": e["title"], "name": e["name"], "value": val})
    if extras:
        meta["extra"] = extras

    # --- the card's own fields ---
    out_card = {
        "promptText": card["positive"] or "",
        "negativePrompt": card["negative"] or "",
        "seed": card["seed"] or "",
        "width": card["width"],
        "height": card["height"],
        "ratio": card["ratio"] or "",
    }
    label = str(fields.get("label") or "").strip()
    if label:
        out_card["label"] = label[:120]
    cat = str(fields.get("category") or "").strip()
    if cat:
        out_card["category"] = cat[:120]
    tags = _split_tags(fields.get("tags"))
    if tags:
        out_card["tags"] = tags
    for src, dst, cap in (("author", "author", 120), ("author_url", "authorUrl", 500), ("source_url", "sourceUrl", 500)):
        v = " ".join(str(fields.get(src) or "").split())
        if v:
            out_card[dst] = v[:cap]
    notes_txt = str(fields.get("notes") or "").strip()
    if notes_txt:
        out_card["comments"] = notes_txt
    if fields.get("protected") is True:
        out_card["nsfw"] = True

    if not out_card["promptText"] and not preview:
        notes.append("No positive prompt found — the card will import without prompt text.")

    return {"card": out_card, "meta": norm_json(meta), "sources": sources, "notes": notes,
            "sampler": sid, "samplers": [{"id": i, "title": r.title(i)} for i in sids],
            "auto_keys": sorted(auto_keys)}


def chunk_payload(built, batch_index=0, batch_size=1):
    """The JSON stored in the PNG's 'promptvault' text chunk."""
    return {
        "pv": PV_FORMAT,
        "card": built["card"],
        "meta": built["meta"],
        "source": {
            "app": "ComfyUI",
            "node": "Prompt Vault Card (Smaller Hammer)",
            "version": NODE_VERSION,
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "batch_index": batch_index,
            "batch_size": batch_size,
        },
    }


def chunk_text(built, batch_index=0, batch_size=1):
    """ASCII-only JSON (non-ASCII escaped), safe for a PNG tEXt chunk."""
    return json.dumps(norm_json(chunk_payload(built, batch_index, batch_size)),
                      ensure_ascii=True, separators=(",", ":"), allow_nan=False)
