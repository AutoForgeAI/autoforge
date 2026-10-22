"""
MIME type registration for static UI assets.

On Windows, Python's ``mimetypes`` module reads extension mappings from the
registry (HKEY_CLASSES_ROOT). Third-party software frequently rewrites those
keys, e.g. mapping ``.js`` or ``.css`` to ``text/plain`` or
``application/x-css``. Starlette's StaticFiles/FileResponse rely on
``mimetypes.guess_type``, so the built UI is then served with the wrong
Content-Type and browsers refuse to apply the stylesheet, execute module
scripts, or render SVG/fonts - leaving an unstyled page (see issue #37).

Registering the correct types explicitly overrides whatever the registry says.
"""

import mimetypes

# Extensions produced by the Vite build (ui/dist) and public assets.
STATIC_MIME_TYPES: dict[str, str] = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".map": "application/json",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".wasm": "application/wasm",
}


def register_static_mime_types() -> None:
    """Force correct MIME types for UI assets, overriding OS-provided mappings."""
    for ext, mime in STATIC_MIME_TYPES.items():
        mimetypes.add_type(mime, ext, strict=True)
