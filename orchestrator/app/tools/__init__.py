"""Project audit tooling (PROMPT 0.5).

Non-destructive audit that cross-references the governance docs in
``/docs/`` against the actual source code, schemas, providers, API
routes, and tests. Reports PASS / WARN / FAIL per dimension.

Run from the orchestrator directory:

    python -m app.tools.project_audit
"""

__all__ = ["main"]
