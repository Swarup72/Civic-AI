# CivicAI Merge Plan

**This is a plan only. No phase below is implemented as part of producing this document.** Per this task's own instructions, implementation begins only after the user has reviewed `MERGE_AUDIT.md`, `MERGE_ARCHITECTURE.md`, and `MERGE_MAPPING.md` and given the go-ahead.

Ordering principle: each phase is independently shippable, depends only on prior phases, touches the smallest possible surface of protected code, and ends with the existing test suite (144 tests) still fully passing plus new tests for whatever the phase added. Frontend and backend work for the same feature are grouped into one phase rather than split, since a dashboard is useless without its endpoint and an endpoint is unverifiable without its dashboard.

---

## Phase 0 — Pre-implementation housekeeping (not a feature; a prerequisite)

**Goal:** clear the two items `MERGE_AUDIT.md` flagged that aren't code changes but should happen before touching anything.

- Confirm with the user whether to delete/purge `repopack-output.txt` (contains a live copy of `FRIEND_PROJECT/server/.env`, including a Supabase service-role key) and whether to rotate that key/the Gemini key if the underlying Supabase project is real.
- Add a root-level `.gitignore` (or a `FRIEND_PROJECT/server/.gitignore` and `FRIEND_PROJECT/.gitignore`) covering `.env` before either project is ever `git init`'d, so this can't recur.
- Get sign-off on the four open items in `MERGE_CONFLICTS.md`'s "Needs product sign-off" list — or at minimum, confirm the recommended defaults stated there are acceptable, so later phases aren't blocked mid-stream.

**Exit criteria:** user has explicitly approved starting Phase 1.

---

## Phase 1 — Frontend role-routing scaffold

**Goal:** the `ProtectedRoute` + role-home-redirect pattern exists and works, with zero new dashboards yet — proven against the existing `AuthorityDashboard.jsx` first, since it's the one real dashboard already there.

- Add `ProtectedRoute.jsx` (new component, `frontend/src/routes/` or alongside existing structure) wired to the existing `useAuth()`/`role`.
- Add a `ROLE_HOME_PATH`-equivalent constant.
- Wrap the existing `/authority` route in `<ProtectedRoute allowedRoles={['authority']}>` as the proof of concept — this is the first real behavior change to verify (a `citizen`-role session hitting `/authority` should now redirect instead of silently rendering).
- Update `Login.jsx` to redirect via `ROLE_HOME_PATH` + honor `location.state.from`, instead of always navigating to `/`.
- **No backend changes in this phase.**

**Depends on:** nothing (independent of every other phase).
**Exit criteria:** existing manual/demo-role-switcher flows still work exactly as before for the citizen/public pages; a non-authority session can no longer land on `/authority` without redirect; existing 144 backend tests untouched and passing (no backend touched); a new, small frontend smoke check (manual or scripted) confirms the redirect behavior for all four roles.

---

## Phase 2 — Citizen Dashboard

**Goal:** an aggregated "my complaints" view, closing the one real citizen-facing gap identified in `MERGE_AUDIT.md`.

- Backend: add an optional `reportedBy: Optional[str]` query param to `GET /api/complaints` (`complaints.py::list_complaints`), following the exact existing pattern used for `category`/`status`/`department` — additive, defaults to no filter, does not change any existing caller's behavior.
- Backend test: `test_complaints.py::test_list_complaints_filtered_by_reported_by` (and a case confirming the filter composes correctly with existing filters/pagination).
- Frontend: new `pages/CitizenDashboard.jsx` (Tailwind), calling `complaintsAPI.list({ reportedBy: user.id })`, reusing the existing `ComplaintCard`/`StatusBadge`/`PriorityBadge` components rather than inventing new ones. Confirm/reject actions call the existing `complaintsAPI.confirm()` — no new endpoint needed (see `MERGE_MAPPING.md`).
- Route it behind `ProtectedRoute` from Phase 1, at whatever path was confirmed in Phase 0's sign-off (`/citizen` new, or reuse `/`).

**Depends on:** Phase 1 (routing scaffold).
**Exit criteria:** a logged-in citizen sees only their own complaints on this new page, with working confirm/reopen actions; existing public feed (`Home.jsx`) behavior is unchanged; new backend test passes alongside all 144 existing ones.

---

## Phase 3 — Government/Authority Dashboard refinement

**Goal:** carry over FRIEND's two genuine UX improvements — one-click acknowledge-as-claim, and a combined note+file resolution form — into the *existing* `AuthorityDashboard.jsx`, without a rewrite.

- No new backend endpoints required — this phase only changes how the existing `AuthorityDashboard.jsx` sequences its existing API calls (`authorityAPI.updateStatus`, `mediaAPI.upload(..., 'evidence')`).
- Combine the currently-separate "upload evidence" and "submit resolution" steps into one form submission, matching FRIEND's `GovernmentDashboard.jsx` interaction (upload proof + note together, one button).
- Add the "Government Authority" display-label mapping decided in `MERGE_CONFLICTS.md` §4 (presentation only).
- Wrap `/authority` fully in `ProtectedRoute` (already done in Phase 1 as the proof-of-concept; this phase is where the surrounding UX polish lands).

**Depends on:** Phase 1.
**Exit criteria:** existing authority workflows (acknowledge, assign, resolve, escalate) all still pass their existing backend tests untouched (no backend change in this phase); a manual/scripted check confirms the combined note+file submission produces the same backend state as the previous two-step flow did.

---

## Phase 4 — NGO Dashboard

**Goal:** the first genuinely new role-scoped screen, closing the "NGO reuses the authority screen verbatim" gap.

- **Pre-requisite:** resolve `MERGE_CONFLICTS.md` items 1 and 2 (NGO direct-transition rights; case-locking on accept) with the user before writing backend code for this phase.
- Backend, if sign-off allows NGO transitions: extend `authority.py`'s guard model (or add a small, parallel `require_role("ngo")`-gated set of transitions scoped to `ESCALATED`/`IN_PROGRESS` complaints already... — exact shape depends on the Phase-0 sign-off outcome) — write this as its own small design note appended to this plan once confirmed, rather than guessing the shape now.
- If case-locking is wanted: add `claimedByOrgId: Optional[str]` to the complaint schema (additive) + a find-then-insert-with-unique-index guard analogous to `supports`.
- Frontend: new `pages/NGODashboard.jsx` (Tailwind), scoped by status filter to escalated/in-progress cases, "Accept Case" action, lock indicator when already claimed.
- New backend tests: `tests/test_ngo_dashboard.py` (or extend `test_ngo_permissions.py`) covering accept-case, double-accept-rejection (if case-locking is built), and resolution-with-evidence for an NGO-held case.

**Depends on:** Phase 1; the Phase-0 sign-off items specific to NGO rights.
**Exit criteria:** an NGO-role session can view escalated cases, accept one, upload resolution evidence, and cannot act on a case another NGO already accepted (if locking was built); all new + existing tests pass.

---

## Phase 5 — Admin Dashboard + Department/Organization management

**Goal:** the largest single addition — real admin capability, matching FRIEND's actual (if Supabase-shaped) functionality, rebuilt on MongoDB.

- Backend: new `app/routes/admin.py`, `require_role("admin")` throughout:
  - `GET/POST /api/admin/departments`, `GET/POST /api/admin/organizations` — new Pydantic schemas (`app/schemas/admin.py` or extend `app/schemas/`), new Mongo collections, indexed the same way existing collections are (name uniqueness, following the `users.email` unique-index pattern).
  - `PATCH /api/admin/users/{id}/role` — role-change endpoint; audit-logged (`audit_service.record("admin_action", ...)` — note `admin_action` already exists in `AUDIT_ACTIONS`, unused until now) and rate-limited like other sensitive writes.
  - `GET /api/admin/overview` — imports and reuses `dashboard.py`'s existing aggregation functions rather than re-querying the database in parallel; adds the new gov-vs-ngo resolution-source split described in `MERGE_MAPPING.md`.
- Seed: add one demo admin user to `backend/seed.py`, following the exact existing pattern (hardcoded id, bcrypt-hashed password, documented in `docs/DEMO_GUIDE.md`).
- Frontend: new `pages/AdminDashboard.jsx` (Tailwind) — KPI tiles, department performance table, per-user role dropdown, add-department form, add-organization form — modeled on FRIEND's `AdminDashboard.jsx` layout but rebuilt against the new FastAPI endpoints, in Tailwind, with no Supabase call anywhere.
- New backend tests: `tests/test_admin.py` — role-gating (non-admin gets 403), department/organization CRUD, role-change audit trail, KPI aggregation correctness.
- Update `docs/RBAC_MATRIX.md` and `docs/api-overview.md` to add the new admin routes, following the existing documentation style (this closes the long-standing documented gap: *"BLOCKED: admin/reviewer roles (needs product decision)"* in `docs/acceptance-criteria.md`).

**Depends on:** Phase 1. Independent of Phases 2-4 (can be built in parallel with them if resourcing allows, since it touches its own new files almost exclusively).
**Exit criteria:** an admin-role session can create a department, register an NGO organization, change a user's role, and view platform-wide KPIs including the gov-vs-ngo split; every admin action appears in the audit log; a non-admin session gets 403 on every admin route; all new + existing tests pass.

---

## Phase 6 — Optional LLM tier for AI classification

**Goal:** fill in the previously-stubbed tier 1 of `ai_service.analyze_complaint()`, using FRIEND's Gemini-call pattern as the reference implementation.

- **Pre-requisite:** confirm the new Python LLM SDK dependency (`MERGE_CONFLICTS.md` §10) is acceptable.
- Backend: implement the actual hosted-LLM call inside `ai_service.py`'s existing `if settings.AI_API_KEY and settings.AI_PROVIDER:` branch (today a no-op `try/except` with a comment) — structured-output call (category/severity/department/`subcategory`/`aiSummary`/reasoning), mapped onto the existing `AIAnalysisResult` shape plus the two new additive fields agreed in `MERGE_MAPPING.md`.
- Map the LLM's raw `severity_score`(0-100)/`priority` onto the existing `SeverityLevel` enum via a small, new, unit-tested bucket function (do not let a raw int leak into the stored `severity` field's type).
- Feed the live `departments` collection (from Phase 5) into the LLM prompt as the candidate list, once it exists — this phase can ship a first version using only the static `CATEGORY_DEPARTMENT_MAP` if Phase 5 hasn't landed yet, then be extended.
- On any LLM failure/timeout/malformed-response, fall through to tier 2 (trained ML) exactly as today — this fallback behavior is the one thing this phase must not weaken, and should have an explicit regression test proving it (simulate an LLM exception, assert the complaint still creates successfully via tier 2/3).
- Surface `aiSummary` into the timeline via the existing `timeline_service.record_event("ai_analysis_completed", ...)` call site in `create_complaint`, using the richer text instead of the current generic message when available.
- New backend tests: `tests/test_ai_llm_tier.py` — successful LLM path (mocked), failure-falls-through path (mocked), disabled-when-unconfigured path (no `AI_API_KEY` set — must behave exactly as today, no behavior change for anyone not opting in).

**Depends on:** nothing structurally, though building it after Phase 5 lets it use the real `departments` collection immediately instead of twice.
**Exit criteria:** with `AI_API_KEY`/`AI_PROVIDER` unset, behavior is byte-for-byte identical to today (verified by re-running the existing AI-related tests unmodified); with them set (test environment, mocked LLM), a complaint gets `subcategory`/`aiSummary` populated and a richer timeline entry; a simulated LLM failure still produces a working complaint via the existing fallback chain.

---

## Phase 7 — Proactive SLA escalation sweep

**Goal:** add the one genuinely new *backend automation* FRIEND demonstrated — periodic auto-escalation on ack-SLA breach — without disturbing the existing lazy `evaluate_sla_status`/`OVERDUE` behavior.

- Backend: new `sla_service.find_ack_breached()` helper (queries complaints in `SUBMITTED`/`ANALYZING`/`OVERDUE` whose `acknowledgmentDeadline` has passed by more than a configurable grace period — not immediately on breach, to avoid flapping against the existing `OVERDUE` transition).
- Refactor `complaints.py::escalate_complaint`'s core logic into a plain function callable both from the route (human-initiated, any role, reason supplied by the caller) and from the new sweep (system-initiated, reason = `"Authority SLA breached: no acknowledgment within required timeframe."`, mirroring FRIEND's own message).
- New `asyncio` background task started in `main.py`'s `lifespan`, running every N minutes (config value, default e.g. 5-15 minutes — not FRIEND's aggressive 60 seconds, since this app's SLA windows are hours/days, not seconds), cancelled cleanly on shutdown.
- Reuse `notification_service.notify_role("ngo", ...)` exactly as the existing manual-escalation path already does — no new notification mechanism.
- New backend tests: `tests/test_sla_sweep.py` — a complaint past its ack deadline gets escalated by the sweep function (called directly in tests, not by waiting on a real timer); a complaint already `RESOLVED`/`CONFIRMED`/`ESCALATED` is never touched by the sweep; the sweep is idempotent (running it twice in a row doesn't double-escalate or double-notify).

**Depends on:** nothing structurally; independent of Phases 2-6.
**Exit criteria:** an ack-SLA-breached complaint left untouched by any human is auto-escalated by the sweep within one interval, with an NGO notification fired exactly once; manual escalation (`POST /complaints/{id}/escalate`) continues to work identically for every role, unchanged.

---

## Phase 8 — Documentation, polish, and final acceptance pass

**Goal:** bring the new surface up to the existing documentation/testing bar before calling the merge done.

- Update `docs/RBAC_MATRIX.md`, `docs/api-overview.md`, `docs/DATABASE_DESIGN.md` (new collections), `docs/acceptance-criteria.md` (close the admin-role and, if Phase 6 shipped, hosted-LLM blockers that are currently listed as BLOCKED).
- Full regression pass: `cd backend && python -m pytest tests/ -v` (target: 144 existing + all new-phase tests, 100% passing) and `cd frontend && npm run build` (must still succeed cleanly).
- Manual/scripted smoke test of all four role dashboards end-to-end, following the same style as the existing "Live smoke test" entries in `docs/acceptance-criteria.md`.
- Verify against `docs/MERGE_ACCEPTANCE.md` (companion document) line by line.

**Depends on:** all prior phases whose features are in scope for this merge round.
**Exit criteria:** every checklist item in `docs/MERGE_ACCEPTANCE.md` is checked off.

---

## Suggested sequencing if parallelized across more than one person

Phase 1 is a hard prerequisite for 2/3/4 only (frontend routing). Phases 5, 6, and 7 are backend-heavy and structurally independent of each other and of 2-4 — they can run in parallel with the frontend phases once Phase 0 sign-off is complete. Phase 8 is last, always.

```
Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──┐
                     ├─▶ Phase 3 ──┤
                     └─▶ Phase 4 ──┤
Phase 0 ──▶ Phase 5 ───────────────┼──▶ Phase 8
Phase 0 ──▶ Phase 6 ───────────────┤
Phase 0 ──▶ Phase 7 ───────────────┘
```

**Reminder: nothing in this plan is implemented yet.** This document defines order and scope for a future implementation pass, pending the user's review of the architecture and mapping documents.
