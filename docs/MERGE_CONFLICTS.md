# CivicAI Merge Conflicts

Every conflict below is a case where YOUR_PROJECT and FRIEND_PROJECT genuinely disagree (different name, different shape, different mechanism, different value) for what is conceptually the same thing. Each has an explicit resolution. None are left open — where a decision needs the user's confirmation before implementation, that is called out under "Needs product sign-off," not left ambiguous.

---

## 1. API conflicts

| Conflict | YOUR_PROJECT | FRIEND_PROJECT | Resolution |
|---|---|---|---|
| API surface / access pattern | All data access goes through versionless REST endpoints under `/api/*`, documented in `docs/api-overview.md`, with FastAPI's auto-generated `/docs` | Frontend calls Supabase's auto-generated PostgREST API directly (`supabase.from('complaints')...`) for almost everything; only 2 real custom HTTP endpoints exist (`/api/complaints/:id/analyze`, `/api/sla/check`) | **Resolved: FastAPI is the only API surface in the final app.** No frontend code calls anything other than `services/api.js`'s wrapped FastAPI endpoints. FRIEND's 2 custom endpoints' logic is absorbed into existing FastAPI services (`ai_service.py`, a new SLA-sweep background task), not exposed as new routes mirroring Express's shape. |
| Claiming/acknowledging a complaint | `PATCH /api/authority/complaints/{id}/status` (generic status-transition endpoint, guarded by `VALID_TRANSITIONS`) | `supabase.rpc('claim_complaint', {p_complaint_id, p_user_id, p_role, p_org_or_dept_id})` — an atomic, role-aware claim operation whose SQL is not in this repo | **Resolved:** no new "claim" endpoint is added. The existing status-transition endpoint already does this (`SUBMITTED → ACKNOWLEDGED`); the *product* idea of "claim" is a one-click frontend affordance that calls the existing endpoint with a fixed target status, not a new backend primitive. If NGO "Accept Case" needs a *different* transition rule than authority acknowledgment (see item 5 below), that is handled inside the existing `VALID_TRANSITIONS`/`require_role` machinery, not a parallel RPC-style endpoint. |

## 2. Schema conflicts

| Conflict | YOUR_PROJECT | FRIEND_PROJECT (inferred) | Resolution |
|---|---|---|---|
| Complaint document/table shape | camelCase Mongo document: `caseId`, `reportedBy`, `priorityScore`, `acknowledgmentDeadline`, `completionEvidenceUrl`, `citizenConfirmation`, `areaId`, GeoJSON `location.geo`, `pendingPhoto` | snake_case Postgres row (reconstructed from client code): `citizen_id`, `department_id`, `severity_score`, `acknowledgment_deadline`, `resolution_deadline`, `assigned_ngo_id`, `support_count`, `image_url`, `address` (free text, no lat/lng) | **Resolved:** the Mongo document shape (`app/schemas/complaint.py`) is authoritative and unchanged. Any new field FRIEND has that's worth adding (`subcategory`, an `ai_summary`/`aiSummary`) is added *additively* to the existing schema — see `MERGE_MAPPING.md`'s AI section — never a wholesale schema swap. `assigned_ngo_id`'s concept (a case is "locked" to whichever NGO accepted it) has no direct YOUR_PROJECT equivalent today; see item 5 below for its resolution. |
| Department / Organization as data | `Department` is a fixed Python `Enum` + a static `CATEGORY_DEPARTMENT_MAP`; no organization/NGO entity at all | `departments` and `organizations` are real, admin-manageable Postgres tables with `id`/`name`(+`contact_email` for orgs) | **Resolved:** two new Mongo collections, `departments` and `organizations`, are added (Pydantic schemas + CRUD in the new `app/routes/admin.py`), additive to, not replacing, the existing `Department` enum (which continues to drive the AI classifier's default category→department mapping; admin-created departments are a separate, evolvable list layered on top — see `MERGE_ARCHITECTURE.md`). |

## 3. Authentication conflicts

| Conflict | YOUR_PROJECT | FRIEND_PROJECT | Resolution |
|---|---|---|---|
| Token mechanism | Custom opaque `"<user_id>.<role>.<hmac_sha256>"`, no expiry, verified via `hmac.compare_digest` | Supabase-issued JWT session, presumably with its own expiry/refresh semantics | **Resolved: YOUR_PROJECT's token scheme is the only one in the final app.** Not combined, not run side-by-side even temporarily. Supabase Auth is fully discarded (architecture mandate: no two competing auth systems). |
| Where role lives | Encoded directly in the signed token AND re-verified against the `users` collection on each request (`auth_utils.py::get_current_user_from_header`) | Looked up separately from a `profiles` table after every sign-in/session-restore (`AuthContext.jsx::fetchProfile`) | **Resolved:** keep YOUR_PROJECT's model (role travels with the token, cross-checked against the DB). FRIEND's separate-profile-fetch pattern is not needed since the token already carries this, and is not adopted. |
| Signup role assignment | Server always forces `role = citizen` on self-registration, ignoring any client-supplied role (`auth.py::register`) | Same behavior: `SignupPage.jsx` always passes `role: ROLES.CITIZEN` in the signup metadata | **No actual conflict — confirmed aligned.** Both sides already agree: self-service signup is citizen-only; authority/NGO/admin accounts are provisioned out-of-band. No change needed. |

## 4. Role naming conflicts

| Conflict | YOUR_PROJECT | FRIEND_PROJECT | Resolution |
|---|---|---|---|
| Government role's wire value | `"authority"` | `"government"` | **Resolved: keep `"authority"`** as the enum/DB/token value — it is threaded through 144 tests, every `require_role("authority")` call site, `backend/seed.py`, and `docs/RBAC_MATRIX.md`. Renaming it would be a large, purely-cosmetic, high-risk change for zero functional gain. |
| User-facing label | "Authority" / "Municipal Authority" in existing UI copy | "Government Official" (`ROLE_LABELS`) | **Resolved:** adopt FRIEND's clearer, more citizen-friendly *label* ("Government Authority") in new/updated frontend copy, mapped from the unchanged `"authority"` value via a simple `ROLE_LABELS` lookup constant (same pattern FRIEND already uses) — a presentation-only change, zero backend impact. |

## 5. Complaint-status conflicts

FRIEND's client code references 8 distinct lowercase status strings; YOUR_PROJECT has 11 distinct uppercase `ComplaintStatus` enum values with an enforced transition graph. They are not the same vocabulary, and a literal string-for-string merge is not possible (case, count, and semantics all differ). Explicit mapping, left-to-right = "FRIEND's status → what it actually corresponds to in YOUR_PROJECT":

| FRIEND status | Nearest YOUR_PROJECT equivalent | Notes |
|---|---|---|
| `submitted` | `SUBMITTED` | Direct match. |
| `ai_analyzed` | `SUBMITTED` (AI analysis already happened synchronously, pre-save, in YOUR_PROJECT — there is no separate "AI has finished" status because AI always finishes before the complaint is even persisted) | Not a gap: FRIEND needs this status because its AI call is decoupled/async after creation; YOUR_PROJECT doesn't need an equivalent status because its AI call is synchronous before creation. No new status added. |
| `acknowledged` | `ACKNOWLEDGED` | Direct match. |
| `in_progress` | `IN_PROGRESS` | Direct match. |
| `escalated` | `ESCALATED` | Direct match. |
| `proof_submitted` | `RESOLVED` + `completionEvidenceUrl` present | See `MERGE_MAPPING.md`; not a new status, a derived UI condition. |
| `resolved` | `CONFIRMED` (citizen-verified) — FRIEND's `resolved` appears to mean "citizen accepted the proof," based on `CitizenDashboard.jsx`'s `handleCloseComplaint(id, confirmed=true)` setting status to `'resolved'` | **Naming collision to resolve carefully:** FRIEND's `resolved` = YOUR_PROJECT's `CONFIRMED` (citizen-verified closure), *not* YOUR_PROJECT's `RESOLVED` (authority claims fixed, awaiting citizen). Do not conflate the two when translating FRIEND's UI copy — a button labeled "Resolved" in a ported screen must map to the `confirm` action/`CONFIRMED` status, not to authority's `RESOLVED` transition. |
| `ai_verified` | No equivalent exists | FRIEND references this value (seen in `AuthorityDashboard`-equivalent status-gating logic) but no code path in the FRIEND client actually sets it — likely set only by Supabase-side logic not in this repo. **Not ported**: YOUR_PROJECT's evidence verification (`/verify-evidence`) already returns a `result` (`not_resolved`/`uncertain`) that is stored on the complaint (`evidenceVerification` field) without needing a dedicated status value; this is judged sufficient and more honest (it never fabricates a confident "verified" result — see `vision_service.py`'s documented honesty stance). |

**No new `ComplaintStatus` enum values are added.** Every FRIEND-side status concept maps onto an existing YOUR_PROJECT status plus, at most, an existing auxiliary field (`completionEvidenceUrl`, `evidenceVerification`). This keeps the tested `VALID_TRANSITIONS` state machine untouched.

## 6. Database model conflicts

| Conflict | Resolution |
|---|---|
| MongoDB documents vs. Postgres/Supabase relational rows | Already resolved in §2/§4 of `MERGE_MAPPING.md`: MongoDB is the only database; nothing from FRIEND's relational schema (foreign keys, RLS policies, the `claim_complaint` stored procedure) is ported as SQL or as a relational pattern. Any needed relationship (e.g., a complaint pointing at a `departmentId`/`organizationId`) is expressed as a plain string reference field, consistent with how `areaId` already works in the existing schema. |
| `assigned_ngo_id` "case lock" concept | FRIEND's schema has a dedicated column so a claimed-by-NGO case can't be claimed by another NGO/authority simultaneously. YOUR_PROJECT's `assignedTo` field today is a free-text string (`authority.py::update_assignment`), not an ownership lock. | **Needs product sign-off** (see below): if concurrent NGO claiming of the same escalated case is a real scenario to prevent, add a small, additive `claimedByOrgId`/`claimedByUserId` field + a guard in the new NGO accept-case endpoint, following the exact same "find-then-insert / unique-index" pattern already used for `supports` (`database.py::ensure_indexes`) to avoid a race condition. This is scoped as part of the NGO Dashboard REBUILD in `MERGE_PLAN.md`, not before. |

## 7. AI conflicts

| Conflict | Resolution |
|---|---|
| Two different "the AI analyzed this" mechanisms (in-process cascade vs. out-of-process Gemini call) | Resolved via COMBINE in `MERGE_MAPPING.md`: FRIEND's Gemini-call *pattern* becomes tier 1 of YOUR_PROJECT's existing (currently stubbed) cascade, called in-process from `ai_service.py` (an `httpx`/`google-genai` Python call, not a Node service), never as a separate Express process. |
| Two different confidence/severity representations (`SeverityLevel` enum vs. `severity_score` 0-100 int, `priority` low/medium/high/critical vs. YOUR_PROJECT's severity-derived label) | When the new LLM tier runs, its raw `severity_score`/`priority` output is mapped down to the existing `SeverityLevel` enum (a simple threshold function, analogous to `priority_service.py::_label_for_score`'s existing bucket logic) before being stored — the stored `aiAnalysis.severity` field's *type* never changes, so every existing reader (priority scoring, SLA calculation, frontend `SLAIndicator`/`PriorityBadge`) keeps working unmodified. The raw `severity_score` can optionally be kept in the new `confidenceBreakdown`-style dict for transparency, not as the primary stored value. |
| Department recommendation: fixed enum+map (YOUR_PROJECT) vs. LLM picks from a live admin-managed list (FRIEND) | Once the new `departments` collection exists (see §2 above), the LLM tier's prompt is given that live list (mirroring FRIEND's `availableDepartments` prompt input) and asked to pick one — but the *fallback* tiers (trained ML, rule-based) continue to use the existing static `CATEGORY_DEPARTMENT_MAP`, since they have no mechanism to reason over an arbitrary admin-defined list. This is a real, accepted asymmetry between tiers, not an oversight — document it in the updated `ai_service.py` docstring when built. |

## 8. Media-storage conflicts

Already fully resolved as DISCARD-of-FRIEND's-mechanism in `MERGE_MAPPING.md` §"Media & evidence." No further ambiguity: Supabase Storage is not used anywhere; local disk + public/private + EXIF-strip is unchanged and unconditional for every media file in the final app, including any new admin-uploaded assets (e.g., an organization logo, if ever added) — same validation path (`media_service.validate_and_decode`), no separate "trusted because it's an admin" bypass.

## 9. Routing conflicts

| Conflict | Resolution |
|---|---|
| FRIEND's routes are role-prefixed (`/citizen`, `/citizen/report`, `/citizen/community`, `/government`, `/ngo`, `/admin`) vs. YOUR_PROJECT's current flat, feature-named routes (`/`, `/report`, `/authority`, `/impact`, `/community`, `/areas`, `/nearby`) | **Needs product sign-off:** two viable options, not silently picked: (a) keep YOUR_PROJECT's existing flat route names and only *add* new routes for the new dashboards (`/citizen-dashboard` or reuse `/` for citizen, `/ngo` new, `/admin` new), preserving every existing bookmark/link; or (b) adopt FRIEND's role-prefixed convention wholesale, which is cleaner long-term but renames `/authority` → `/government` or keeps `/authority` inconsistently alongside new `/ngo`/`/admin`/`/citizen` routes. **Recommended default if no preference is given:** option (a) — add `/ngo` and `/admin` as new routes, keep everything else's URL exactly as today, since nothing requires the rename and it avoids breaking any existing deep link during the merge. This default is recorded in `MERGE_PLAN.md`; flag before Phase 2 if a different choice is wanted. |
| FRIEND's layout-shell pattern (`MainLayout`/`AuthLayout`/`DashboardLayout` wrapping `<Outlet/>`) vs. YOUR_PROJECT's single flat `App.jsx` with one global `Navbar` | **Resolved:** adopt a `DashboardLayout`-equivalent wrapper *only* for the four new/updated role dashboards (so they can share a consistent dashboard-specific sub-nav later if wanted), while the existing public pages (`Home`, `Landing`, `CommunityFeed`, etc.) keep using the current flat `App.jsx` + global `Navbar` structure unchanged. This is additive, not a full router rewrite. |

## 10. Package conflicts

| Package | YOUR_PROJECT | FRIEND_PROJECT | Resolution |
|---|---|---|---|
| React | 18.2.0 | 19.2.8 | Stay on 18.2.0 (per `MERGE_MAPPING.md`); do not install 19.x anywhere in the final app. |
| react-router-dom | 6.22.3 | 7.18.3 | Stay on 6.22.3. FRIEND's `ProtectedRoute`/`AppRoutes` patterns are reimplemented against v6's API (which already supports everything used — `<Navigate>`, `useLocation().state`, nested `<Route element={<Layout/>}>`), so no v7-only API is actually needed. |
| Vite | 5.1.6 | 8.3.0 | Stay on 5.1.6. |
| Express | — (not present) | 5.2.1 | Not installed. Per the architecture mandate ("MUST NOT use Express as the primary backend"), Express is not added to the final app in any capacity, including as a small auxiliary service. |
| `@supabase/supabase-js` | — | 2.116.0 (both client and server) | Not installed anywhere in the final app. |
| `@google/genai` (Gemini SDK) | — | 2.22.0 (server only) | **New, small dependency to add to `backend/requirements.txt`** (or the equivalent official `google-genai` Python package) — this is the one FRIEND dependency actually needed, to implement the new LLM tier in `ai_service.py`. Confirm this is an acceptable "small new dependency" under the task's constraint before Phase 6 of `MERGE_PLAN.md` (it is a single well-maintained SDK, not a framework swap, but flagged explicitly since the task says not to install large new dependencies without noting them). |
| `nodemon` | — | 3.1.14 (Express dev-reload) | Not installed; irrelevant once Express itself is discarded. |
| `cors` (npm) | — (FastAPI's own `CORSMiddleware` is used instead) | 2.8.6 | Not installed; YOUR_PROJECT's existing `CORSMiddleware` configuration in `main.py` is unchanged and sufficient. |
| Tailwind CSS | 3.4.1 | — (absent) | No conflict — FRIEND simply doesn't have it; every ported page is written in Tailwind from the start. |

## 11. Environment-variable conflicts

| Variable | YOUR_PROJECT | FRIEND_PROJECT | Resolution |
|---|---|---|---|
| `MONGODB_URI`, `DATABASE_NAME`, `CORS_ORIGINS`, `UPLOAD_DIR`, `SECRET_KEY` | Required, already defined | N/A | Unchanged. |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` | Defined, currently unused (stub) | N/A (FRIEND uses `GEMINI_API_KEY` directly) | **Resolved:** once the LLM tier is implemented, `AI_PROVIDER=gemini`/`AI_API_KEY=<key>`/`AI_MODEL=gemini-3.6-flash` (or whichever model is current) becomes the actual configuration read by `ai_service.py` — reusing the *existing* variable names rather than introducing a parallel `GEMINI_API_KEY` variable, so no new env-var name is added to `backend/.env.example` beyond documenting the expected value for `AI_PROVIDER`. |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `PORT` (Express) | — | Defined in `FRIEND_PROJECT/server/.env` and `client/.env.local`/`.env.example` | **None of these are carried into the final app.** They belong exclusively to the discarded Supabase/Express layer. See `MERGE_AUDIT.md` §12 for the associated secrets-exposure finding regarding these specific values. |
| `GEMINI_API_KEY` | — | Defined in `FRIEND_PROJECT/server/.env` | **Not reused as a variable name.** If the same underlying key/project is reused for the new LLM tier, its value is placed under the existing `AI_API_KEY` variable name in `YOUR_PROJECT/backend/.env` (never committed), not copied into a new `GEMINI_API_KEY` variable — keeping one consistent provider-agnostic variable name regardless of which hosted LLM is configured. |

---

## Needs product sign-off before implementation (collected)

1. **NGO direct status-transition rights** (§6): should an NGO be able to transition a complaint's status directly (mirroring authority's rights, scoped to escalated cases it has accepted), or only "accept" (claim) + upload evidence, with an authority or the existing escalation flow handling the rest? Affects whether `VALID_TRANSITIONS`/`require_role` gains an NGO branch.
2. **Case-locking on NGO accept** (§6): is concurrent double-claiming of an escalated case by two NGOs a real risk worth a dedicated unique-claim field, or is today's simple `assignedTo` free-text field sufficient given expected usage scale?
3. **Route naming convention** (§9): keep flat existing route names + add `/ngo`, `/admin` (recommended default), or adopt FRIEND's role-prefixed convention across the board?
4. **New LLM dependency** (§10): confirm installing an official Gemini/LLM Python SDK is acceptable as the one exception to "no large new dependencies," given it directly fulfills the architecture's own "optional LLM" slot.

None of these block writing `MERGE_PLAN.md`'s phase structure (each is scoped to a specific phase where it can be confirmed just-in-time), but all four should be confirmed before their respective phase begins implementation.
