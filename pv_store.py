"""
Shortname table for Prompt Vault Card — stored in ComfyUI's user folder so it
survives updating or reinstalling this node pack, and applies to every workflow.

    <ComfyUI>/user/smallerhammer/pv_shortnames.json   {"file.safetensors": "Short"}

Copyright (c) 2026 Smaller Hammer - MIT Licence
"""

import json
import os

import folder_paths

from .pv_core import clean_shortnames


def shortnames_path():
    base = folder_paths.get_user_directory()
    return os.path.join(base, "smallerhammer", "pv_shortnames.json")


def load_shortnames():
    try:
        with open(shortnames_path(), encoding="utf-8") as f:
            return clean_shortnames(json.load(f))
    except (OSError, ValueError):
        return {}


def save_shortnames(data):
    clean = clean_shortnames(data)
    path = shortnames_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)
    return clean
