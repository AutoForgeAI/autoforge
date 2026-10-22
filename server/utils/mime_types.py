"""
MIME Type Registration
======================

On Windows, Python's ``mimetypes`` module seeds its table from the registry
(HKEY_CLASSES_ROOT). Third-party software frequently overwrites the
``Content Type`` for common web extensions there, e.g. mapping ``.css`` or
``.js`` to ``text/plain`` or ``application/x-css``. Starlette's StaticFiles and
FileResponse use ``mimetypes.guess_type()``, so the UI would be served with the
wrong Content-Type and browsers refuse to apply the stylesheet / execute the
module script - the page renders as unstyled HTML (see issue #37).

Registering the correct types explicitly makes static serving independent of
the host's registry.
"""

import mimetypes

# Extensions emitted by the Vite build (ui/dist) and files in ui/public.
WEB_MIME_TYPES: dict[str, str] = {
    ".css": "text/css",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".json": "application/json",
    ".map": "application/json",
    ".html": "text/html",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".wasm": "application/wasm",
}


def register_web_mime_types() -> None:
    """Override registry-derived MIME types for web assets. Safe to call repeatedly."""
    # add_type() calls mimetypes.init() first if needed, so the registry is read
    # before our entries are applied and cannot clobber them afterwards.
    for ext, mime in WEB_MIME_TYPES.items():
        mimetypes.add_type(mime, ext, strict=True)
