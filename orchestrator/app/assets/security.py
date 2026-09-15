"""
SVG security validation — shared by Character and Asset systems.

Prevents:
    - Path traversal (e.g. `../../etc/passwd`)
    - Unsafe filesystem paths
    - Malicious SVG (scripts, event handlers)
    - External URL injection (image hrefs to http://, file://, etc.)
    - Script injection (onclick, onload, onerror, etc.)
    - Invalid MIME type
    - Unexpected file extensions

The validator is shared across Character and Asset systems to ensure
consistent security standards.

Code reused from character/svg_generator.py to avoid duplication.
"""
from __future__ import annotations

import re
from pathlib import Path

_SCRIPT_TAG = re.compile(r"<\s*script\b", re.IGNORECASE)
_EVENT_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
_EXTERNAL_HREF = re.compile(r"\b(href|xlink:href)\s*=\s*[\"']\s*(https?:|file:|javascript:|data:)",
                              re.IGNORECASE)
_JAVASCRIPT_URI = re.compile(r"javascript:", re.IGNORECASE)
_SVG_ELEMENT = re.compile(r"<\s*svg\b", re.IGNORECASE)


def validate_svg(content: str) -> tuple[bool, list[str]]:
    """Validate an SVG string for security risks.

    Returns:
        (is_safe, list_of_warnings)
    """
    errors: list[str] = []

    if not content or not content.strip():
        errors.append("Empty SVG content")
        return (False, errors)

    if not _SVG_ELEMENT.search(content):
        errors.append("SVG does not contain <svg> element")

    if _SCRIPT_TAG.search(content):
        errors.append("SVG contains <script> tag")

    if _EVENT_HANDLER.search(content):
        errors.append("SVG contains event handlers")

    if _EXTERNAL_HREF.search(content):
        errors.append("SVG references external resources")

    if _JAVASCRIPT_URI.search(content):
        errors.append("SVG contains javascript: URI")

    return (len(errors) == 0, errors)


def validate_path(file_path: str | Path) -> tuple[bool, list[str]]:
    """Validate a filesystem path for security.

    Prevents:
        - Path traversal (../)
        - Absolute system paths (e.g. /etc/, C:\\windows)
        - Unsupported file extensions
    """
    errors: list[str] = []
    path = Path(file_path)

    # Check for path traversal patterns
    parts = path.parts
    if ".." in parts:
        errors.append(f"Path contains '..': {file_path}")

    # Check for absolute system paths
    if path.is_absolute():
        if str(path).startswith(("/etc", "/usr", "C:\\Windows", "C:\\Program Files")):
            errors.append(f"Path appears unsafe: {file_path}")

    # Check extension
    valid_exts = {".png", ".jpg", ".jpeg", ".svg", ".json", ".webp"}
    if path.suffix.lower() not in valid_exts:
        errors.append(f"Unexpected file extension: {path.suffix}")

    return (len(errors) == 0, errors)


def validate_mime(mime_type: str) -> bool:
    """Validate a MIME type string."""
    valid_mimes = {
        "image/png",
        "image/jpeg",
        "image/svg+xml",
        "image/webp",
        "application/json",
    }
    return mime_type in valid_mimes


def safe_filename(name: str) -> str:
    """Sanitize a filename to be filesystem-safe."""
    # Remove path separators and shell-metacharacters
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    # Strip leading dots to avoid hidden files
    safe = safe.lstrip(".")
    if not safe:
        safe = "unnamed"
    return safe
