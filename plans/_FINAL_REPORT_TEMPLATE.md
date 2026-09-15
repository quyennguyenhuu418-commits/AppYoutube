# Final Report Template

Append this section at the bottom of every plan **after** the implementation
phase is complete. Copy the contents below into the plan file under a
`## Final Report` heading, fill in the placeholders, and save.

---

## Final Report

### 1. Files Created This Session

| Path | Lines | Purpose |
|------|-------|---------|
| `<absolute path>` | `<N>` | `<one-line description>` |
| `<absolute path>` | `<N>` | `<one-line description>` |

### 2. Files Modified This Session

| Path | Delta | Purpose |
|------|-------|---------|
| `<absolute path>` | `+<N>/-<M>` | `<one-line description of what changed>` |
| `<absolute path>` | `+<N>/-<M>` | `<one-line description of what changed>` |

### 3. Cumulative Project Summary

**What exists now**

<one paragraph describing the current overall state of the project after this prompt and all previous prompts>

**Subsystems completed**

- `<subsystem name>` — `<one-line summary>`
- `<subsystem name>` — `<one-line summary>`

**Subsystems not yet started**

- `<subsystem name>` — `<one-line summary of why deferred>`
- `<subsystem name>` — `<one-line summary of why deferred>`

**Known limitations**

- `<limitation>` — `<impact and workaround>`
- `<limitation>` — `<impact and workaround>`

**Next prompt focus**

<one sentence describing what the next prompt should tackle, based on remaining subsystems and known limitations>

---

## Notes for reuse

- This template is intentionally markdown-only and self-contained so it can
  be pasted into any plan file.
- The "Files Created / Modified" sections are the canonical record of work
  in that prompt. Keep the absolute paths so future prompts can re-audit.
- The "Cumulative Project Summary" should be rewritten (not copied verbatim)
  each prompt so it always reflects the current state, not the state at
  plan creation time.
- Tables are preferred over bullet lists in sections 1 and 2 because the
  columns are short, stable, and easy to diff across prompts.
