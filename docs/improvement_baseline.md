# Improvement Baseline

This document tracks the high-impact hotspots that were validated before refactoring and the implementation actions taken.

## Backend hotspots

- Sync SQLAlchemy calls were running in many `async def` API handlers.
  - Action: Converted DB-heavy handlers to `def` in customer, preset, config matrix, notes, audit, and login submit endpoints.
- Repeated soft-delete actor resolution across routers.
  - Action: Added `app/common/entity_ops.py` and reused `mark_soft_deleted()` in multiple routers.
- Schema browser flags existed but were not fully enforced.
  - Action: Schema routes are now mounted only when `ENABLE_SCHEMA_BROWSER=true`.
- Schema export and row counting could be expensive.
  - Action: Added configurable count behavior and export limits/streaming in schema router.
- Audit failures were swallowed silently.
  - Action: Middleware now logs audit write failures without blocking request flow.

## Frontend / UX hotspots

- List pages used blocking `alert()` dialogs for many errors.
  - Action: Added global `AdminToast` helper and migrated pages to toast-based feedback.
- Pagination and empty/error row rendering were duplicated across pages.
  - Action: Added shared `AdminListUI` helpers and wired list pages to use them.
- Inline style usage and drawer-width drift.
  - Action: Replaced inline styles with reusable CSS classes in schema/preset templates.
- Accessibility and motion consistency gaps.
  - Action: Added `:focus-visible` styles and `prefers-reduced-motion` fallback in CSS.

## Feature enhancements shipped

- Bulk delete actions for customers, presets, and config matrix entries.
- Customer activity timeline endpoint and UI panel.
- Effective-date conflict detection for config assignments (backend validation + UI feedback).
