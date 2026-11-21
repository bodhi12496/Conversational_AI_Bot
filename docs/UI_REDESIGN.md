# UI redesign — 21 November 2026

The original single-screen workbench mixed data setup, persistent edits, agent configuration, publishing and read-only questions. This update separates them into six task-focused pages, using enterprise workspace conventions informed by Snowflake Semantic Studio and Wren AI modeling documentation.

- Overview: four-step setup guide, project counts, recent questions and clear next action. Completion indicators reflect observable model state; a saved definition is not proof of correctness.
- Data sources: upload dialog with drag/drop and file picker, sample-data onboarding, searchable source inventory, row counts and snapshot import dates.
- Semantic model: per-view explorer, columns/metrics/relationships/instructions tabs, readable relationship cards and a conversational edit dialog with explicit preview and draft-save actions.
- Agent setup: select views, review and apply the selection, inspect validations/assumptions, and explicitly publish. Unsaved selections disable publishing.
- Chat: dedicated conversation surface, suggestions drawn from the actual published model, result tables and expandable calculation evidence. Questions remain independent; no backend conversational memory was added.
- Activity & versions: version history, restore-as-new-draft, question history, and reference tests with a basic form plus an advanced JSON option.

The visual system uses a white sidebar, blue active states, consistent table and card styles, clear page headings, restrained badges, responsive layouts, keyboard focus styles, modal focus containment and descriptive accessible controls. Mobile navigation scrolls horizontally; API connection settings remain available in the top bar.

The backend APIs and domain behavior are unchanged. No unsupported connector or hosting controls are presented as functional.

References:
- https://docs.snowflake.com/en/user-guide/views-semantic/semantic-studio
- https://docs.getwren.ai/cp/guide/modeling/overview

Validation: the 37 backend tests pass; TypeScript/Vite build passes. The real-API DOM integration walkthrough is recorded after final validation. Chromium execution is blocked by this environment's socket restrictions, so rendered desktop/mobile appearance is not visually verified here; an updated browser smoke test is included.
