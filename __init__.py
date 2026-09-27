"""Minimal ComfyUI entry point. No dependencies are installed on import."""
WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

try:
    from .bridge import register
    register()
except Exception:
    import logging
    logging.getLogger("MTools").exception("M Tools bridge unavailable; ComfyUI can continue")

__all__ = ["WEB_DIRECTORY", "NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
