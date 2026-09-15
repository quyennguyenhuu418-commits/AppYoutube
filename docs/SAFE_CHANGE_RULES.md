# SAFE_CHANGE_RULES

14 rules every AI coding session in this repository must follow. These
exist to prevent architectural drift, contract duplication, and silent
test-status inflation.

---

## 1. Read project memory before coding

Before touching any file, read (in order):

1. `docs/PROJECT_CONTEXT.md`
2. `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. The relevant contract doc (`DATA_CONTRACTS.md`, `API_CONTRACTS.md`,
   `PROVIDER_REGISTRY.md`, `PIPELINE_REGISTRY.md`)
5. The actual source code
6. `docs/TEST_STATUS.md`
7. `docs/TECHNICAL_DEBT.md`
8. `docs/SAFE_CHANGE_RULES.md` (this file)

---

## 2. Inspect actual code before architectural changes

Do not infer architecture from filenames or documentation. Open the
relevant files, read the imports, trace the call graph.

---

## 3. Search before creating new components

Before adding a new schema, API route, provider, or stage, grep the
repository for similar functionality:

- `grep -r "<symbol>" orchestrator/app/`
- `grep -r "<symbol>" renderer/src/`
- `grep -r "<symbol>" webapp/`

If a near-duplicate exists, reuse it. Do not create parallel contracts.

---

## 4. Reuse canonical contracts

Use the existing canonical contracts (see `docs/DATA_CONTRACTS.md`). Do
not invent new contracts for data already covered. If you need a new
field, add it to the existing model with a default value and an
optional-flag where possible (avoid breaking changes).

---

## 5. Never duplicate schemas

If a new model would overlap with an existing one, extend the existing
model. Document the addition in `docs/CHANGELOG_INTERNAL.md`.

---

## 6. Never duplicate APIs

If a new route would overlap with an existing one, extend the existing
route. Document in `docs/API_CONTRACTS.md`.

---

## 7. Never silently change contract ownership

If a contract moves from one producer to another (e.g., `ResearchPackage`
canonical becoming the only contract), update `docs/DATA_CONTRACTS.md`,
`docs/PROVIDER_REGISTRY.md`, `docs/PIPELINE_REGISTRY.md`, and
`docs/CHANGELOG_INTERNAL.md` in the same change.

---

## 8. Never modify database destructively

There is no database yet, but if one is added (see
`docs/TECHNICAL_DEBT.md` C-006, C-012):

- Never drop a column without a migration path.
- Never delete a row without retention policy.
- Never change a primary key in place.
- Always write a migration file under `migrations/` (does not exist yet).

---

## 9. Never modify SceneDefinition without dependency analysis

SceneDefinition is the single cross-runtime contract. Any change to
`orchestrator/app/schemas/scene_definition.py` MUST also update
`renderer/src/scenes/types.ts` in the same change. Document the change
in `docs/DATA_CONTRACTS.md` C-01.

---

## 10. Never mark tests passed without runtime evidence

Update `docs/TEST_STATUS.md` only with actual command output. Statuses
`PASSED` and `FAILED` require recorded exit codes. Use `BLOCKED` if the
runtime cannot run (e.g., Python not installed).

---

## 11. Never silently refactor unrelated modules

Touch only the files required by the prompt's scope. Other modules must
not be modified. If a refactor is needed, propose it in a separate
prompt.

---

## 12. Never remove code without impact analysis

Before deleting any function, class, file, or contract:

1. Grep for all usages (`grep -r "<symbol>"`).
2. Identify all callers and consumers.
3. Confirm no tests depend on it.
4. Update `docs/DATA_CONTRACTS.md`, `docs/API_CONTRACTS.md`,
   `docs/PROVIDER_REGISTRY.md`, or `docs/PIPELINE_REGISTRY.md` if
   applicable.
5. Update `docs/CHANGELOG_INTERNAL.md`.

---

## 13. Never change architecture without recording an ADR

Major architectural decisions (new runtime, new persistence layer, new
provider type, new contract ownership) MUST be captured as a new ADR in
`docs/ARCHITECTURE_DECISIONS.md`. The ADR must cite code evidence.

---

## 14. Stop on unresolved HIGH or CRITICAL conflicts

If a new prompt uncovers a HIGH or CRITICAL conflict not already in
`docs/TECHNICAL_DEBT.md`, STOP. Add the conflict to that file, propose a
resolution in the Final Report, and do NOT fix it in the same prompt
unless the prompt explicitly authorizes it.

---

## End-of-Prompt Checklist

Before declaring any prompt complete:

1. Run tests (`pytest`, `vitest`, or `python -m app.tools.project_audit`).
2. Run project audit and confirm no new conflicts.
3. Check downstream contracts — did the change break any consumer?
4. Update `docs/PROJECT_STATE.md`.
5. Update `docs/CHANGELOG_INTERNAL.md`.
6. Update `docs/TEST_STATUS.md`.
7. Update `docs/KNOWN_LIMITATIONS.md` if any new limitation was
   discovered.
8. Write Final Report per `plans/_FINAL_REPORT_TEMPLATE.md`.
9. STOP.
