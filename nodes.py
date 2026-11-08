"""
Prompt Vault Card and Prompt Vault Save Image — Smaller Hammer nodes for ComfyUI.

The Card node gathers a Prompt Vault card (prompt, negative, seed, size,
ratio, category, tags…) plus the generation settings (model, CLIP, VAE,
LoRAs, sampler and any ticked extras). The Save node writes it into each PNG
as a 'promptvault' text chunk, next to ComfyUI's usual metadata, so Prompt
Vault can fill in the card on import.

Copyright (c) 2026 Smaller Hammer - MIT Licence
"""

import json
import os

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths

from . import pv_core
from .pv_store import load_shortnames


def _parse_json(raw, default):
    try:
        v = json.loads(raw or "")
        return v if isinstance(v, type(default)) else default
    except (ValueError, TypeError):
        return default


def _metadata_disabled():
    try:
        from comfy.cli_args import args
        return bool(args.disable_metadata)
    except Exception:
        return False


def pv_pnginfo(pv_card, batch_index, batch_size, prompt=None, extra_pnginfo=None, standard=True):
    """PngInfo with ComfyUI's usual chunks (unless disabled) and the promptvault chunk."""
    info = PngInfo()
    if standard and not _metadata_disabled():
        if prompt is not None:
            info.add_text("prompt", json.dumps(prompt))
        for k, v in (extra_pnginfo or {}).items():
            info.add_text(k, json.dumps(v))
    if pv_card:
        # Written even with --disable-metadata: wiring a card in is an explicit request.
        info.add_text(pv_core.PV_CHUNK_KEY, pv_core.chunk_text(pv_card, batch_index, batch_size))
    return info


class SH_PromptVaultCard:
    """Build a Prompt Vault card from this workflow."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "category": ("STRING", {"default": "", "placeholder": "Category (created on import if missing)"}),
                "tags": ("STRING", {"default": "", "placeholder": "Tags, comma separated"}),
                "label": ("STRING", {"default": "", "placeholder": "Variant name (optional)"}),
                "notes": ("STRING", {"default": "", "multiline": True,
                                     "placeholder": "Notes (optional — embedded in the image only if filled in)"}),
                "protected": ("BOOLEAN", {"default": False, "label_on": "Protected", "label_off": "Not protected",
                                          "tooltip": "Mark the card Protected in Prompt Vault. Off by default: it is written into the image in plain text."}),
                # Managed by the node's panel; hidden in the frontend.
                "overrides": ("STRING", {"default": "{}"}),
                "selection": ("STRING", {"default": '{"v":1,"keys":[]}'}),
            },
            "optional": {
                # Credit fields. Optional so workflows saved with v1.0 keep their widget values aligned.
                "author": ("STRING", {"default": "", "placeholder": "Prompt author (optional)"}),
                "author_url": ("STRING", {"default": "", "placeholder": "Author URL (optional)"}),
                "source_url": ("STRING", {"default": "", "placeholder": "Image source URL (optional)"}),
                "positive": ("STRING", {"forceInput": True, "tooltip": "Wired input wins over the traced prompt"}),
                "negative": ("STRING", {"forceInput": True}),
                "seed": ("INT", {"forceInput": True}),
                "width": ("INT", {"forceInput": True}),
                "height": ("INT", {"forceInput": True}),
                "ratio": ("STRING", {"forceInput": True, "tooltip": "e.g. 16:9"}),
            },
            "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("PV_CARD", "STRING")
    RETURN_NAMES = ("pv_card", "card_json")
    FUNCTION = "build"
    CATEGORY = "Smaller Hammer/Prompt Vault"
    DESCRIPTION = "Build a Prompt Vault card (prompt, settings, LoRAs) to embed in saved images."

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def build(self, category, tags, label, notes, protected, overrides, selection,
              author="", author_url="", source_url="", positive=None, negative=None, seed=None, width=None, height=None, ratio=None,
              prompt=None, unique_id=None):
        wired = {"positive": positive, "negative": negative, "seed": seed,
                 "width": width, "height": height, "ratio": ratio}
        sel = _parse_json(selection, {}).get("keys", [])
        built = pv_core.build_card(
            prompt or {}, card_id=unique_id,
            fields={"category": category, "tags": tags, "label": label,
                    "notes": notes, "protected": protected, "author": author,
                    "author_url": author_url, "source_url": source_url},
            wired=wired, overrides=_parse_json(overrides, {}),
            selection=set(map(str, sel)), shortnames=load_shortnames())
        payload = pv_core.norm_json(pv_core.chunk_payload(built))
        built["payload"] = payload   # ready-made chunk for other save nodes (e.g. Prompt List Save)
        text = json.dumps(pv_core.norm_json(payload), indent=2, ensure_ascii=False)
        ui = {"text": [json.dumps({"payload": pv_core.norm_json(payload), "sources": built["sources"],
                                   "notes": built["notes"]}, ensure_ascii=False)]}
        return {"ui": ui, "result": (built, text)}


class SH_PromptVaultSave:
    """Save images as PNG with the Prompt Vault card embedded."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "pv_card": ("PV_CARD",),
                "filename_prefix": ("STRING", {"default": "PromptVault"}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Smaller Hammer/Prompt Vault"
    DESCRIPTION = "Save PNGs with a 'promptvault' chunk that Prompt Vault reads on import."

    def save(self, images, pv_card, filename_prefix, prompt=None, extra_pnginfo=None):
        out_dir = folder_paths.get_output_directory()
        h, w = images[0].shape[0], images[0].shape[1]
        full, name, counter, subfolder, prefix = folder_paths.get_save_image_path(
            filename_prefix, out_dir, w, h)
        results = []
        n = len(images)
        for i, image in enumerate(images):
            arr = np.clip(255.0 * image.cpu().numpy(), 0, 255).astype(np.uint8)
            fname = f"{name}_{counter:05}_.png"
            info = pv_pnginfo(pv_card, i, n, prompt, extra_pnginfo)
            Image.fromarray(arr).save(os.path.join(full, fname), pnginfo=info, compress_level=4)
            results.append({"filename": fname, "subfolder": subfolder, "type": "output"})
            counter += 1
        return {"ui": {"images": results}}


NODE_CLASS_MAPPINGS = {
    "SH_PromptVaultCard": SH_PromptVaultCard,
    "SH_PromptVaultSave": SH_PromptVaultSave,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SH_PromptVaultCard": "Prompt Vault Card (Smaller Hammer)",
    "SH_PromptVaultSave": "Prompt Vault Save Image (Smaller Hammer)",
}
