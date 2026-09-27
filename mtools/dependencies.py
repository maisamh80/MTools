"""Explicit widget adapters; unknown/dynamic dependencies remain unresolved."""
from pathlib import Path
from .files import inside

ADAPTERS = {
    "CheckpointLoaderSimple": [(0, "checkpoints")],
    "CheckpointLoader": [(1, "checkpoints")],
    "UNETLoader": [(0, "diffusion_models")],
    "DiffusionModelLoader": [(0, "diffusion_models")],
    "CLIPLoader": [(0, "text_encoders")],
    "DualCLIPLoader": [(0, "text_encoders"), (1, "text_encoders")],
    "TripleCLIPLoader": [(0, "text_encoders"), (1, "text_encoders"), (2, "text_encoders")],
    "VAELoader": [(0, "vae")],
    "LoraLoader": [(0, "loras")],
    "LoraLoaderModelOnly": [(0, "loras")],
    "ControlNetLoader": [(0, "controlnet")],
    "DiffControlNetLoader": [(0, "controlnet")],
    "CLIPVisionLoader": [(0, "clip_vision")],
    "UpscaleModelLoader": [(0, "upscale_models")],
    "StyleModelLoader": [(0, "style_models")],
    "GLIGENLoader": [(0, "gligen")],
}
INPUT_NAMES = {"checkpoints": {"ckpt_name"}, "diffusion_models": {"unet_name", "model_name"},
               "text_encoders": {"clip_name", "clip_name1", "clip_name2", "clip_name3"},
               "vae": {"vae_name"}, "loras": {"lora_name"}, "controlnet": {"control_net_name"},
               "clip_vision": {"clip_name"}, "upscale_models": {"model_name"}}
# Only nodes with no external file requirements belong here. Everything else is conservative.
PURE = {"ModelSamplingAuraFlow", "KSampler", "KSamplerAdvanced", "CLIPTextEncode", "VAEDecode", "VAEEncode",
        "EmptyLatentImage", "EmptySD3LatentImage", "SaveImage", "PreviewImage", "Reroute",
        "Note", "MarkdownNote", "ConditioningCombine", "ConditioningConcat", "ConditioningSetArea",
        "LatentUpscale", "LatentUpscaleBy", "ImageScale", "ImageScaleBy", "SetLatentNoiseMask"}


def validate_graph(graph):
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise ValueError("Import a ComfyUI workflow graph JSON, not an API prompt")
    if len(graph["nodes"]) > 10000:
        raise ValueError("Too many workflow nodes")
    for node in graph["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("type"), str):
            raise ValueError("Invalid workflow node")
    return graph


def analyze(graph, host):
    validate_graph(graph)
    refs, customs, unresolved = [], {}, []
    roots = host.get("model_roots", {})
    registry = host.get("nodes", {})
    nodes = list(graph["nodes"])
    definitions = graph.get("definitions", {}).get("subgraphs", [])
    for definition in definitions:
        nodes.extend(definition.get("nodes", []))
    subgraph_ids = {d.get("id") for d in definitions}
    for node in nodes:
        kind, node_id = node["type"], str(node.get("id", "?"))
        info = registry.get(kind)
        if info and info.get("custom"):
            customs[kind] = {"type": kind, "status": "loaded", **info}
        elif not info and kind not in {"Reroute", "Note", "MarkdownNote"} and kind not in subgraph_ids:
            customs[kind] = {"type": kind, "status": "missing"}
        if kind in subgraph_ids:
            continue
        if kind == "CLIPTextEncode" and any(isinstance(v, str) and "embedding:" in v.lower() for v in node.get("widgets_values", [])):
            unresolved.append({"node_id": node_id, "type": kind, "status": "unsupported",
                               "reason": "Text references embeddings; verify and include these files manually"})
        if kind not in ADAPTERS:
            if kind not in PURE:
                unresolved.append({"node_id": node_id, "type": kind, "status": "unsupported",
                                   "reason": "No deterministic dependency adapter; inspect this node"})
            continue
        values = node.get("widgets_values", [])
        for index, category in ADAPTERS[kind]:
            ref = {"node_id": node_id, "type": kind, "category": category, "status": "unsupported"}
            linked = any(i.get("name") in INPUT_NAMES.get(category, set()) and i.get("link") is not None
                         for i in node.get("inputs", []))
            name = values[index] if isinstance(values, list) and index < len(values) else None
            if linked or not isinstance(name, str) or not name:
                ref["reason"] = "Model input is linked or its widget layout is unsupported"
            else:
                ref["name"] = name
                matches = []
                for root in roots.get(category, []):
                    try:
                        p = inside(root, name.replace("\\", "/"))
                        if p.is_file():
                            matches.append(str(p))
                    except (ValueError, OSError):
                        pass
                ref["matches"] = matches
                ref["status"] = "found" if len(matches) == 1 else "ambiguous" if matches else "missing"
                if len(matches) == 1:
                    ref["source"] = matches[0]
                    try:
                        ref["target"] = Path(matches[0]).relative_to(Path(host["models"])).as_posix()
                    except ValueError:
                        ref["status"] = "external"
                        ref["reason"] = "External model found; portable destination requires explicit mapping"
            refs.append(ref)
    ready = all(r["status"] == "found" for r in refs) and not unresolved and all(c["status"] == "loaded" for c in customs.values())
    return {"status": "complete" if ready else "needs_attention", "models": refs,
            "custom_nodes": list(customs.values()), "unresolved": unresolved,
            "notice": "File availability only; Python packages, hardware and successful execution are not verified."}
