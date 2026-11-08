"""ComfyUI-SmallerHammer-PromptVault — Copyright (c) 2026 Smaller Hammer - MIT Licence"""
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

try:
    from . import routes  # noqa: F401  (live card preview and shortnames)
except Exception as e:
    print(f"[Smaller Hammer Prompt Vault] routes not loaded: {e}")

WEB_DIRECTORY = "./web/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
