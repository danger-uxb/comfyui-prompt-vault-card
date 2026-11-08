"""
API routes for the Prompt Vault Card node's panel: a live preview of the card
before you run, and the shortname table.

Copyright (c) 2026 Smaller Hammer - MIT Licence
"""

import json

from aiohttp import web
from server import PromptServer

from . import pv_core
from .pv_store import load_shortnames, save_shortnames

ROUTE = "/smallerhammer/promptvault"


@PromptServer.instance.routes.post(f"{ROUTE}/resolve")
async def pv_resolve(request):
    try:
        body = await request.json()
        prompt = body.get("prompt") or {}
        card_id = body.get("card_id")
        built = pv_core.build_card(
            prompt, card_id=card_id, fields=body.get("fields") or {},
            overrides=body.get("overrides") or {}, selection=set(body.get("selection") or []),
            shortnames=load_shortnames(), preview=True)
        entries = pv_core.list_entries(prompt, card_id)
        files = sorted({e["value"] for e in entries
                        if pv_core.MODEL_EXT.search(e["value"] or "") and "\n" not in e["value"]})
        payload = pv_core.chunk_payload(built)
        return web.json_response({
            "ok": True,
            "card": built["card"], "meta": built["meta"], "sources": built["sources"],
            "notes": built["notes"], "sampler": built["sampler"], "samplers": built["samplers"],
            "auto_keys": built["auto_keys"], "entries": entries, "files": files,
            "chunk": json.dumps(pv_core.norm_json(payload), indent=2, ensure_ascii=False),
        })
    except Exception as ex:
        return web.json_response({"ok": False, "error": str(ex)})


@PromptServer.instance.routes.get(f"{ROUTE}/shortnames")
async def pv_shortnames_get(request):
    return web.json_response({"ok": True, "shortnames": load_shortnames()})


@PromptServer.instance.routes.post(f"{ROUTE}/shortnames")
async def pv_shortnames_set(request):
    try:
        body = await request.json()
        return web.json_response({"ok": True, "shortnames": save_shortnames(body.get("shortnames") or {})})
    except Exception as ex:
        return web.json_response({"ok": False, "error": str(ex)})
