# CivicAI Merge Audit

**Phase:** Inspection only. No code has been merged, deleted, moved, or modified as part of this audit.
**Scope:** `YOUR_PROJECT/` (canonical backend + current frontend) vs `FRIEND_PROJECT/` (Supabase/Express prototype with role-dashboard UX).
**Method:** Every claim below was verified by reading the actual source in both repos (not inferred from README claims). Line/file references are given so any claim can be re-checked.

---

## 0. Repository shape at a glance

| | YOUR_PROJECT | FRIEND_PROJECT |
|---|---|---|
| Top-level dirs | `backend/`, `frontend/`, `docs/`, `test-data/` | `client/`, `server/` |
| Backend LOC (routes+services+schemas) | ~3,500+ lines, 9 route modules, 13 service modules | 103 lines total (`server/index.js` + 2 service files) |
| Frontend pages/components | 24 files, ~3,050 lines | 14 files, role dashboards ~150-260 lines each |
| Automated tests | 20 backend test files, **144 passing pytest tests** (per `docs/acceptance-criteria.md`) | **0 tests** (`server/package.json`'s `test` script is a stub: `echo "Error: no test specified" && exit 1`) |
| Markdown docs | 17 files in `docs/` + root-level `decision.md`, `flow.md`, `CivicAI_Antigravity_Project_Context.md` | 1 file: `PROJECT_SPEC.md` (feature list, no implementation detail) + generic Vite template `client/README.md` |
| Own git history | None (no `.git` in either project or at the integration root) | None |

**Headline finding:** FRIEND_PROJECT is not a parallel "mature backend, different stack" implementation — it is a thin Express shim (2 HTTP routes, both delegating to Supabase) sitting in front of a Supabase/Postgres project whose schema, RLS policies, and `claim_complaint` stored procedure are **not present in this repo at all**. Its real value is entirely in `client/src/pages/dashboards/*` and the routing/role pattern around them — a product-and-UX contribution, not a backend architecture to adopt, consistent with the task's framing.

---

## 1. Architecture overview

| Layer | YOUR_PROJECT | FRIEND_PROJECT |
|---|---|---|
| Frontend framework | React 18.2, Vite 5.1, react-router-dom 6.22 | React 19.2, Vite 8.3, react-router-dom 7.18 |
| Styling | Tailwind CSS 3.4 (+ `tailwind.config.js`, `postcss.config.js`) + custom "glassmorphism" utility classes | **No Tailwind anywhere** — hand-written CSS custom properties (`index.css`) + inline `style={{}}` objects on every element |
| HTTP client | `axios`, one `services/api.js` module wrapping every backend route | Direct `@supabase/supabase-js` client calls scattered through every page component; one raw `fetch()` to the Express server (fire-and-forget AI trigger) |
| Backend framework | **FastAPI** (Python 3.12), `uvicorn`/ASGI, Pydantic v2 schemas, auto `/docs` | **Express 5** (Node/ESM), 2 routes, no schema validation library |
| Business logic location | In-repo: `app/services/*.py` (13 modules) | Almost entirely **outside this repo**: Supabase Postgres functions/RLS/triggers implement `claim_complaint`, role checks, and presumably the department/organization tables — none of that SQL exists in `FRIEND_PROJECT/` |
| Database | MongoDB via Motor, **with a fully-featured in-memory fallback** (`app/database.py`) that mimics the Mongo cursor/insert/update API so every route works identically in both modes | Supabase (managed Postgres) — no local/offline fallback of any kind; the app is non-functional without a live Supabase project |
| Auth | Custom HMAC-SHA256 signed opaque tokens (`app/auth_utils.py`), bcrypt password hashing, role resolved server-side from the `users` collection | Supabase Auth (hosted JWT/session), role resolved client-side by querying a `profiles` table row after sign-in |
| File storage | Local filesystem, `uploads/public` (served) + `uploads/private` (never served), EXIF-aware | Supabase Storage (`complaints` bucket), public URLs only |
| AI | In-process: trained TF-IDF+LogisticRegression classifier (`ml_service.py`) with a documented rule-based fallback (`ai_service.fallback_analyze_text`); a "hosted LLM" tier is **hooked but never implemented** (`settings.AI_API_KEY`/`AI_PROVIDER` are read, then nothing happens) | Out-of-process HTTP call from Express to Google Gemini (`@google/genai`, model `"gemini-3.6-flash"`) with a structured JSON response schema |
| Vision/image AI | Scaffolded, honestly reports `available: false` (`vision_service.py`) since no model is trained; classical-CV scene-match (ORB+RANSAC) is real and working (`scene_match_service.py`) | None — FRIEND never inspects image content or location-matches proof photos |

---

## 2. Frontend differences

- **Routing model.** YOUR_PROJECT's `App.jsx` (`YOUR_PROJECT/frontend/src/App.jsx`) registers every page (`Home`, `ReportProblem`, `AuthorityDashboard`, `ImpactDashboard`, `CommunityFeed`, `AreaDashboard`, `NearbyComplaints`, `Login`, `Register`) flat, with **no route guard component at all** — anyone can navigate to `/authority` by URL regardless of role; RBAC is enforced only server-side (explicitly documented as intentional in `docs/RBAC_MATRIX.md`: *"Frontend button visibility is never treated as a security control anywhere in this app"*). FRIEND_PROJECT has a real `ProtectedRoute` (`client/src/routes/ProtectedRoute.jsx`) that redirects unauthenticated users to `/login` and wrong-role users to their own role's home path (`ROLE_HOME_PATH` lookup), plus three distinct layout shells (`MainLayout`, `AuthLayout`, `DashboardLayout`).
- **Role-specific screens.** YOUR_PROJECT has one shared `AuthorityDashboard.jsx` used by both the "authority" and "ngo" demo roles (confirmed: it has no NGO-specific view — the demo-role switcher just changes the auth token, the page content doesn't branch on role), one `ImpactDashboard.jsx` (public transparency analytics, not an admin control panel), and no per-citizen "my complaints" dashboard (`Home.jsx` is the *public* feed, not filtered to `reportedBy === currentUser.id` — verified by grep, no such filter exists). FRIEND has **four genuinely distinct dashboard components**: `CitizenDashboard`, `GovernmentDashboard`, `NGODashboard`, `AdminDashboard`, each with role-specific data fetches and actions.
- **Styling system mismatch.** FRIEND's dashboards are unstyled by today's target design system (no Tailwind, inline styles, `var(--accent)` CSS variables) — every one of them needs a visual rebuild, not a copy-paste, to fit YOUR_PROJECT's Tailwind/glassmorphism look.
- **State/data-fetching pattern.** YOUR_PROJECT centralizes all HTTP calls in `services/api.js`; FRIEND calls `supabase.from(...)` directly inside page components (no service layer at all), including direct writes to a `complaint_updates` table from the client — a pattern that would bypass FastAPI, audit logging, and timeline_service entirely if copied as-is.
- **Auth UX difference worth keeping the idea of, not the code:** FRIEND's `location.state.from` redirect-after-login pattern (`ProtectedRoute.jsx` → `LoginPage.jsx`) is a nice-to-have UX FRIEND has and YOUR_PROJECT's `Login.jsx` does not (`YOUR_PROJECT` always navigates to `/` after login).

## 3. Backend differences

- YOUR_PROJECT's backend is the entire application's logic surface: 9 routers, 13 services, a real state machine (`authority.py::VALID_TRANSITIONS`), rate limiting, audit logging, a typed timeline, notifications, geo resolution (circle + polygon), SLA due-soon math, and a documented AI cascade.
- FRIEND's backend (`server/index.js`) is 103 lines implementing exactly two things: (1) `POST /api/complaints/:id/analyze` — call Gemini, write the result back to Supabase, insert one `complaint_updates` row; (2) `POST /api/sla/check` plus a `setInterval(..., 60_000)` background sweep that finds complaints past `acknowledgment_deadline` still `submitted`/`ai_analyzed` and flips them straight to `escalated`. Every other piece of "backend logic" visible in the FRIEND frontend (claiming a case, role checks, resolving, confirming) is a **direct Supabase table write from the browser** or a call to a Postgres RPC function (`claim_complaint`) whose definition is not in this repository at all — it cannot be audited or ported, only its *effect* can be inferred from the calling code.
- **This is the single most important backend-differences finding:** there is no "FRIEND_PROJECT backend architecture" to compare against FastAPI feature-for-feature. There is a 2-endpoint Node shim plus an opaque hosted database doing row-level security and stored-procedure logic outside version control.

## 4. Database differences

- YOUR_PROJECT: MongoDB documents, camelCase fields, collections `users`, `complaints`, `media`, `supports`, `escalations`, `areas`, `notifications`, `audit_logs`, `timeline_events`, `status_history`, `user_area_memberships` — all defined and indexed in `app/database.py::ensure_indexes` (`docs/DATABASE_DESIGN.md`). A parallel in-memory implementation (`InMemoryDatabase`/`InMemoryCollection`) mimics the same async cursor API so every route is dual-mode-correct by construction, not by a separate code path.
- FRIEND: implied Postgres/Supabase relational schema (snake_case: `complaints`, `complaint_updates`, `complaint_supports`, `profiles`, `departments`, `organizations`) with foreign keys and at least one stored procedure (`claim_complaint(p_complaint_id, p_user_id, p_role, p_org_or_dept_id)`). **No SQL/migration files exist in `FRIEND_PROJECT/`** — the schema is reconstructed here only from the columns referenced in `.jsx` files (`departments.id/name`, `organizations.id/name/contact_email`, `profiles.id/first_name/last_name/username/role/department_id/organization_id`).
- Real, portable gap: YOUR_PROJECT has **no first-class "Department" or "Organization (NGO)" collection** — `Department` is a hardcoded `Enum` (`app/schemas/enums.py`) with a static `CATEGORY_DEPARTMENT_MAP`, and there is no NGO-organization entity at all. FRIEND's admin-manageable departments/organizations tables represent a genuine missing data model, not just a missing screen.

## 5. Authentication differences

- YOUR_PROJECT: self-hosted. Register/login issue an opaque signed token `"<user_id>.<role>.<hmac_sha256>"` (`app/auth_utils.py::sign_token`/`verify_token`), verified with `hmac.compare_digest` against `settings.SECRET_KEY`. Passwords are bcrypt-hashed (`password_service.py`) with a documented transparent-migration path off a legacy unsalted-SHA256 scheme. No token expiration or revocation exists (a documented, deliberate blocker — `docs/acceptance-criteria.md`: *"BLOCKED: token expiration/revocation (needs session-length decision)"*).
- FRIEND: Supabase Auth (hosted, email/password, presumably with its own JWT + refresh-token lifecycle and email confirmation flow — `SignupPage.jsx` handles a `confirmationSent` state). Role is **not** part of the auth token at all; it's a separate `profiles.role` column looked up after every sign-in (`AuthContext.jsx::fetchProfile`, `LoginPage.jsx`'s manual re-fetch after `signIn`).
- **These are two structurally incompatible systems** (opaque HMAC token vs. hosted JWT+session), and the architecture mandate explicitly forbids two competing auth systems in the final app. FRIEND's auth *code* cannot be merged in any form; only the **product pattern** — a `profiles`-style role lookup, protected routes, role-home redirect — is portable, rebuilt against YOUR_PROJECT's existing `AuthContext`/`authAPI`.

## 6. AI differences

- YOUR_PROJECT's `analyze_complaint()` (`app/services/ai_service.py`) documents and implements a 3-tier cascade: hosted LLM (stubbed, never actually calls out) → trained ML classifier (`ml_service.py`, real, trained, confidence-gated) → rule-based keyword fallback (`fallback_analyze_text`, always available). Output shape: `category`, `severity`, `department`, `affectedUsersEstimate`, `locationSensitivity`, `reason`, ack/resolution SLA hours/days, `confidence`, `analyzedBy`, `source`, `needsReview`.
- FRIEND's Express `analyzeComplaint()` (`server/services/aiService.js`) is a **working example of exactly the tier YOUR_PROJECT left unimplemented** — a real hosted-LLM call (Google Gemini) with a schema-constrained JSON response: `category`, `subcategory`, `severity_score` (0-100 integer, not a bucketed enum), `priority` (`low|medium|high|critical`), `recommended_department_id` (chosen from a live list of real departments passed into the prompt), `estimated_resolution_days`, `ai_summary`, `reasoning`.
- Two genuinely new fields FRIEND has that YOUR_PROJECT doesn't: **`subcategory`** (finer-grained than the 10 fixed categories) and a **free-text `ai_summary`** written into the visible complaint history (`complaint_updates`) — YOUR_PROJECT's `aiAnalysis.reason` is stored but not surfaced as a chat-log-style note the way FRIEND's is.
- FRIEND's SLA-escalation worker is **proactive** (a `setInterval` sweep that actively flips status and notifies), while YOUR_PROJECT's `evaluate_sla_status()` is **reactive/lazy** (only recomputed when a complaint is read — `list_complaints`/`get_complaint_details` call it inline). YOUR_PROJECT already auto-transitions to `OVERDUE` this way, but never auto-transitions to `ESCALATED` — that always requires a human/role action today (`complaints.py::escalate_complaint`). A periodic sweep that auto-escalates on ack-SLA breach is a real, missing capability FRIEND demonstrates the value of.

## 7. Media differences

- YOUR_PROJECT: local disk, Pillow-decoded and re-verified (never trusts the client's declared content-type or extension), EXIF/GPS extracted server-side (`media_service.py::extract_exif_gps`), a **public copy with EXIF fully stripped and downsized** vs. a **private original with EXIF intact**, the private original gated to the complaint's owner or an authority (`media.py::_get_owned_complaint_or_403`), a max of 6 files/complaint, 8MB/file. Resolution-evidence photos are automatically compared against the original report photo via classical CV (`scene_match_service.py`, ORB+RANSAC — real, tested, advisory-only).
- FRIEND: Supabase Storage public bucket, no EXIF handling of any kind (GPS-tagged originals would be served publicly, unstripped — a real privacy regression if copied as-is), no scene-match / duplicate-location check on proof photos, no file-count/type/size validation visible in the client code (would rely entirely on Supabase Storage's own bucket policy, which isn't in this repo).
- **Do not port FRIEND's media pattern.** YOUR_PROJECT's public/private + EXIF-strip design is a protected capability per this task's own instructions, and it is strictly more correct than what FRIEND does.

## 8. Role differences

- Role values: YOUR_PROJECT = `citizen | authority | ngo | admin` (`app/schemas/enums.py::UserRole`). FRIEND = `citizen | government | ngo | admin` (`client/src/lib/roles.js::ROLES`). Same four-role shape, one naming collision (`authority` vs `government`) — see `MERGE_CONFLICTS.md`.
- YOUR_PROJECT's `admin` role is **enum-only** — it exists in the type, is accepted by a couple of `require_role("authority", "admin")` gates (`audit.py`) and ownership-or-role checks (`media.py`, `complaints.py`), but there is **no admin user ever seeded** (`backend/seed.py` seeds only citizen/authority/ngo demo accounts), no admin-only route, no admin login path, and no admin UI anywhere in the frontend. This is explicitly documented as a known blocker: `docs/acceptance-criteria.md`: *"BLOCKED: admin/reviewer roles (needs product decision)."*
- FRIEND's `admin` role is the **only one of the two projects that actually implements admin capability**: `AdminDashboard.jsx` reads/writes departments, organizations, and per-user role, and computes platform-wide KPIs — real, if Supabase-shaped, functionality.

## 9. Dashboard differences

| Dashboard | YOUR_PROJECT today | FRIEND_PROJECT |
|---|---|---|
| Citizen | No dedicated "my complaints" view; citizen participates via the public feed (`Home.jsx`) + per-complaint detail page (`ComplaintDetails.jsx`, which **does** already have confirm/reopen actions — see note below) | `CitizenDashboard.jsx`: complaints filtered to `citizen_id === user.id`, inline Accept-and-Close / Reject-and-Escalate actions shown specifically when `status === 'proof_submitted'` |
| Government/Authority | `AuthorityDashboard.jsx`: list + detail-panel split view, status-transition modal, evidence upload, escalate action — full-featured and backed by the real state machine | `GovernmentDashboard.jsx`: same list+detail split idea, "claim/acknowledge" action via `claim_complaint` RPC, resolution-proof upload form inline in the detail panel |
| NGO | **No distinct NGO UI** — NGO demo role reuses `AuthorityDashboard.jsx` verbatim | `NGODashboard.jsx`: scoped to `escalated`/`in_progress`/`proof_submitted` cases, "Accept Case" action, a lock indicator when a case is already claimed |
| Admin | **Does not exist.** `ImpactDashboard.jsx` is the closest analog but is a *public* transparency page (stats/category-summary/monthly-trends), not an admin control panel — it has no user-management, department-management, or organization-management capability | `AdminDashboard.jsx`: KPI tiles (total/pending/escalated/resolved/gov-solved/ngo-solved), department performance table, per-user role dropdown, add-department form, add-NGO-organization form |

**Important correction to a plausible but wrong assumption:** the citizen confirm/reopen *capability* is not missing from YOUR_PROJECT — it's implemented and tested server-side (`complaints.py::citizen_confirm`) and already has frontend UI on the per-complaint detail page (`ComplaintDetails.jsx`, confirmed via grep: `handleConfirmResolution`, `status === "RESOLVED"` gated buttons). What's missing is the **aggregated, role-scoped dashboard view** of "my complaints in this state," not the underlying action.

## 10. Testing differences

- YOUR_PROJECT: 144 passing pytest tests (`docs/acceptance-criteria.md`) across auth, complaints, status transitions, authority permissions, NGO permissions, media, evidence verification, location, community, dashboard, duplicate detection, GeoJSON polygons, SLA due-soon, vision service, dashboard enrichment, audit log, notifications, rate limiting — run against an isolated in-memory DB (`conftest.py` overrides `MONGODB_URI` to an unreachable address so tests never touch a real cluster). No frontend automated tests (documented blocker).
- FRIEND_PROJECT: zero automated tests of any kind, front or back (`server/package.json`'s `test` script literally errors out by design — the default `npm init` stub, never replaced).

## 11. Documentation differences

- YOUR_PROJECT: 17 markdown docs covering database design, security audit, security checklist, RBAC matrix, media privacy, ML evaluation, ML labeling guide, vision-model workflow, implementation status/audit/plan, acceptance criteria, API overview, demo guide, manual test checklist — all clearly dated, self-correcting (each doc states what supersedes it), and cross-referenced.
- FRIEND_PROJECT: one product-spec file (`PROJECT_SPEC.md`, a bullet-point feature list, no implementation detail, no security notes, no data-model documentation) plus the unmodified generic Vite template `README.md`.

## 12. Security differences

- **Authorization enforcement location.** YOUR_PROJECT enforces every role/ownership check server-side and documents this as an explicit invariant (`docs/RBAC_MATRIX.md`). FRIEND's authorization model is **entirely external to this repo** — it depends on Supabase Row-Level Security policies and the `claim_complaint` RPC's internal logic, neither of which is present to audit. A merge that trusted FRIEND's client-side role checks (e.g., `ProtectedRoute`'s `allowedRoles`) as the actual security boundary would be a real regression; they are UX-only, exactly like YOUR_PROJECT's own documented stance on frontend checks.
- **Media privacy.** FRIEND has no public/private split and no EXIF stripping — copying its upload pattern verbatim would leak GPS-tagged originals publicly. Already covered in §7.
- **Password/session handling.** YOUR_PROJECT: bcrypt, no expiry (documented gap). FRIEND: delegated entirely to Supabase Auth (opaque from this repo's point of view).
- **Rate limiting.** YOUR_PROJECT has a real (in-memory, single-process, documented-limitation) rate limiter on login and uploads (`rate_limit_service.py`). FRIEND has none visible in this repo (would depend on Supabase's own defaults, if any).
- **Audit logging.** YOUR_PROJECT has a dedicated, forbidden-key-sanitizing audit log (`audit_service.py`) separate from the citizen-facing timeline. FRIEND has no audit log at all — `complaint_updates` rows are a user-facing history, not a security audit trail, and there is no `admin_action` logging equivalent.

### Secrets scan (existence and location only — no values reproduced, per this task's rule)

| File | Keys present | Committed to git? | Notes |
|---|---|---|---|
| `YOUR_PROJECT/backend/.env` | `MONGODB_URI`, `DATABASE_NAME`, `CORS_ORIGINS`, `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `UPLOAD_DIR`, `SECRET_KEY` | No — covered by `YOUR_PROJECT/.gitignore` (`backend/.env`, `*.env`, with `!*.env.example` carve-out); no git repo exists yet anyway | `docs/SECURITY_AUDIT.md` already documents that this file "currently holds a live MongoDB Atlas credential" and that `SECRET_KEY` is a hackathon placeholder shared with `.env.example` |
| `YOUR_PROJECT/backend/.env.example` | Same key names, placeholder values | N/A (meant to be committed) | — |
| `FRIEND_PROJECT/server/.env` | `PORT`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | **No `.gitignore` exists anywhere in `FRIEND_PROJECT/` (neither at its root nor inside `server/`)** — if this project were ever `git init`'d and committed as-is, this file, including a Supabase **service-role key** (a full-privilege key that bypasses Row-Level Security), would be committed | **Highest-severity finding in this audit** — flagged below |
| `FRIEND_PROJECT/client/.env.local` | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | Covered by `FRIEND_PROJECT/client/.gitignore`'s `*.local` pattern | Lower sensitivity (anon key is designed to be client-exposed), but still real project-identifying config |
| `FRIEND_PROJECT/client/.env.example` | Same two keys, placeholder values | N/A (meant to be committed) | — |

**🔴 Critical, currently-active finding:** `/Users/swaruppal/Desktop/CIVIC-AI integration/repopack-output.txt` (923,639 bytes, sitting at the integration root, outside both project folders, untracked by any git repo) is a full repo-dump/concatenation of both projects' source, and it **embeds the complete plaintext contents of `FRIEND_PROJECT/server/.env`** (confirmed at line 2664: `File: FRIEND_PROJECT/server/.env`, followed by its contents) — meaning the Supabase service-role key and Gemini API key currently exist in plaintext a second time, in a file that looks like disposable tooling output and is easy to forget about, copy elsewhere, or accidentally attach/upload. It also embeds `YOUR_PROJECT/backend/.env.example` (placeholder-only, harmless) but **not** `YOUR_PROJECT/backend/.env` itself (that real secret was correctly excluded when the dump was generated). **Recommended immediate action (outside this audit's no-changes rule, for the user to decide):** delete or securely purge `repopack-output.txt`, and rotate the Supabase service-role key and Gemini API key referenced in `FRIEND_PROJECT/server/.env` if that project's Supabase instance is a real, live project rather than disposable dev scaffolding. No secret value from any of these files is reproduced anywhere in this audit or its companion documents.

---

## Summary verdict

FRIEND_PROJECT contributes **no backend architecture** worth adopting (its real backend logic lives in an un-auditable hosted Supabase project) and **no frontend design system** worth adopting (no Tailwind, inline styles). What it contributes, genuinely and worth carrying forward, is a **product specification expressed as working code**: four distinct role-scoped dashboards, a protected-route/role-home-redirect pattern, an admin control panel (user/department/NGO management + platform KPIs), a working example of an LLM-based triage tier, and a proactive SLA-escalation sweep. Every one of these should be **rebuilt** against YOUR_PROJECT's FastAPI/MongoDB/Tailwind stack, not copied. See `MERGE_MAPPING.md` for the feature-by-feature decision and `MERGE_PLAN.md` for the build order.
