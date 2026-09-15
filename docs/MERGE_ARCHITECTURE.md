# CivicAI Final Architecture

This defines the target architecture the merge builds toward. It is **YOUR_PROJECT's existing architecture, extended additively** — nothing protected is replaced; new capability (role dashboards, admin management, an LLM tier, proactive SLA escalation) is layered onto the existing FastAPI/MongoDB backbone.

---

## 1. Top-level flow

```
                                   ┌───────────────────────────────────────────┐
                                   │                 FRONTEND                   │
                                   │   React 18 + Vite + Tailwind CSS           │
                                   │   react-router-dom 6                       │
                                   │                                             │
                                   │   Public pages   Role dashboards (NEW gate) │
                                   │   Home, Landing,  ┌─────────────────────┐  │
                                   │   Community,      │  ProtectedRoute      │  │
                                   │   Areas, Nearby,   │  (role, redirect)    │  │
                                   │   Report, Details  ├─────────────────────┤  │
                                   │                    │ Citizen Dashboard*   │  │
                                   │                    │ Authority Dashboard  │  │
                                   │                    │ NGO Dashboard*       │  │
                                   │                    │ Admin Dashboard*     │  │
                                   │                    └─────────────────────┘  │
                                   │        (* = new in this merge)              │
                                   └───────────────────┬─────────────────────────┘
                                                        │  axios ⟶ services/api.js
                                                        │  Authorization: Bearer <hmac token>
                                                        ▼
                                   ┌───────────────────────────────────────────┐
                                   │                  FASTAPI                   │
                                   │   app/main.py — CORS, static /uploads,     │
                                   │   lifespan (DB connect, ensure_indexes,    │
                                   │   ensure_default_areas, NEW: start SLA     │
                                   │   sweep background task)                   │
                                   │                                             │
                                   │   Routers (/api/*):                        │
                                   │   auth · complaints · authority · media ·  │
                                   │   areas · community · dashboard ·          │
                                   │   audit · notifications ·                  │
                                   │   NEW: admin                               │
                                   │                                             │
                                   │   Cross-cutting: auth_utils.require_role,  │
                                   │   Pydantic schemas (app/schemas/*)         │
                                   └───────────────────┬─────────────────────────┘
                                                        │  every route delegates
                                                        │  business logic down
                                                        ▼
                                   ┌───────────────────────────────────────────┐
                                   │                 SERVICES                   │
                                   │  (app/services/*.py — the only place       │
                                   │   business rules live; routes stay thin)   │
                                   └───────────────────┬─────────────────────────┘
                                                        │
                                                        ▼
                                   ┌───────────────────────────────────────────┐
                                   │                 MONGODB                    │
                                   │   Motor async client                       │
                                   │   ⇅ automatic fallback ⇅                   │
                                   │   InMemoryDatabase (same cursor API)       │
                                   │                                             │
                                   │  Collections: users, complaints, media,     │
                                   │  supports, escalations, areas,              │
                                   │  notifications, audit_logs,                 │
                                   │  timeline_events, status_history,           │
                                   │  user_area_memberships,                     │
                                   │  NEW: departments, organizations            │
                                   └─────────────────────────────────────────────┘
```

**Nothing above the MongoDB line is optional** for any request — there is no path from the frontend to the database that skips FastAPI (unlike FRIEND_PROJECT's direct-Supabase-client pattern, which is explicitly not carried forward — see `MERGE_CONFLICTS.md` §1).

---

## 2. The services layer, and how the named subsystems relate

The task requires this document to show the relationship between: text ML, optional LLM, vision, geo, SLA, audit, timeline, and notification. All eight already exist as (or, for the LLM, are added as a sibling to) modules in `app/services/`, coordinated through exactly two call sites: **complaint creation** and **complaint resolution/lifecycle transitions**. Nothing calls these services directly except the route layer — no service calls another service's *route*, only its functions, keeping the dependency graph one-directional.

```
                         ┌─────────────────────────┐
                         │   ai_service.py          │   analyze_complaint()
                         │   (orchestrator)         │   — the ONE entry point
                         └────────┬────────┬────────┘     every caller uses
                                  │        │
                    tier 1        │        │  tier 2
                    (NEW)         │        │
                                  ▼        ▼
                    ┌─────────────────┐  ┌──────────────────┐
                    │ optional LLM     │  │  ml_service.py    │   tier 3 (always available):
                    │ (Gemini via      │  │  (trained TF-IDF  │   ai_service.fallback_analyze_text()
                    │  google-genai,   │  │  + LogisticReg.   │   — rule-based, in-process,
                    │  behind          │  │  classifier,      │   never fails
                    │  AI_PROVIDER/    │  │  backend/ml/)     │
                    │  AI_API_KEY)     │  │                   │
                    └─────────────────┘  └──────────────────┘
                    Only runs if configured.  Runs if a model     Runs if the above
                    Falls through to tier 2    file exists at     two are unavailable
                    on any failure/timeout.    backend/ml/models. or fail. Documented,
                                                                    honest, always on.
```

`analyze_complaint()` is called from exactly one place today (`complaints.py::create_complaint`), synchronously, before the complaint document is ever written — this is why YOUR_PROJECT never needed FRIEND's separate `ai_analyzed` status: the AI result is already final by the time `SUBMITTED` is the complaint's first-ever status.

```
                    complaint created (category, severity, department, aiAnalysis)
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  priority_service.py     │  calculate_priority_score()
                    │  (severity 40% +         │  — depends on AI's severity output
                    │   affected 20% +         │    and geo's locationSensitivity,
                    │   support 15% +          │    re-run on every support/unsupport
                    │   location 15% +         │
                    │   duration 10%)          │
                    └─────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  sla_service.py          │  calculate_deadlines() at creation
                    │  (ack + resolution        │  evaluate_sla_status() on every read
                    │   deadlines; due-soon)    │  NEW: periodic background sweep
                    │                           │       (see §3 below) auto-escalates
                    └─────────────────────────┘        breached-ack complaints
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │  geo_service.py          │  build_geojson_point(), resolve_area()
                    │  (haversine + 2dsphere,  │  — runs once at creation (assigns
                    │   circle + polygon       │    areaId/areaName) and on-demand
                    │   areas, find_nearby)    │    for /nearby, /areas/*, /community/*
                    └─────────────────────────┘
```

Independently of the creation flow, three cross-cutting services observe (never gate) every state change:

```
    every meaningful action (create, status change, media upload, escalate,
    confirm, admin action, ...) fans out to THREE independent observers —
    none can block the action, and none replaces another:

    ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
    │ timeline_service.py│   │  audit_service.py  │   │notification_service│
    │ citizen-facing,    │   │ security-facing,   │   │.py                 │
    │ role-aware public/ │   │ forbidden-key-      │   │ per-recipient rows,│
    │ internal split     │   │ sanitized, closed   │   │ role-broadcast     │
    │ ("what happened    │   │ action vocabulary   │   │ fan-out            │
    │ to my complaint")  │   │ ("who did what,     │   │ ("tell this user   │
    │                    │   │ for security review")│  │ something happened")│
    └───────────────────┘   └───────────────────┘   └───────────────────┘
```

`vision_service.py` (image-content AI) and `scene_match_service.py` (classical-CV location matching) sit specifically inside the evidence-verification path, not the creation path:

```
    POST /complaints/{id}/media (media_type=evidence)
                    │
                    ▼
    scene_match_service.compare_scenes()  — ALWAYS runs, real, ORB+RANSAC
                    │
                    ▼
    POST /complaints/{id}/verify-evidence (on-demand, decoupled)
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
    vision_service        scene_match_service
    .compare_before_after()  .compare_scenes() (re-checked)
    ALWAYS reports            ALWAYS available
    available:false today
    (honest, not fabricated;
    becomes real the day a
    trained model exists,
    per backend/ml/vision/)
```

## 3. New capability, and exactly where it attaches

### 3a. Admin routes + Department/Organization model

```
    app/routes/admin.py  (NEW, require_role("admin"))
         │
         ├── GET/POST /api/admin/departments  ──▶  departments collection (NEW)
         ├── GET/POST /api/admin/organizations ─▶  organizations collection (NEW)
         ├── PATCH /api/admin/users/{id}/role  ──▶  existing users collection
         └── GET /api/admin/overview           ──▶  reuses dashboard.py's existing
                                                     aggregation functions (imported,
                                                     not duplicated) + a new gov-vs-ngo
                                                     resolution-source split
```

`departments`/`organizations` are referenced by string id from complaints (`departmentId`, mirroring the existing `areaId` pattern) — additive fields, not a schema migration of existing documents (documents without them simply have `departmentId: None` and continue resolving department via the existing static `CATEGORY_DEPARTMENT_MAP`, exactly as today).

### 3b. Proactive SLA escalation sweep

```
    app/main.py::lifespan()
         │
         └── asyncio.create_task(sla_sweep_loop())   NEW, started at startup,
                                                       cancelled at shutdown
                     │
                     │  every N minutes (config, e.g. 5)
                     ▼
              sla_service.find_ack_breached()   NEW helper, reuses existing
                     │                          evaluate_sla_status() logic
                     ▼
              complaints.escalate_complaint()-equivalent   (refactored to be
                     │                                      callable from both
                     │                                      the route AND the
                     ▼                                      sweep)
              notification_service.notify_role("ngo", ...)  (existing, unchanged)
```

This is an in-process `asyncio` background task, not a separate worker process or a Node-style `setInterval` — consistent with FastAPI's existing `lifespan` pattern already used for DB connection and default-area seeding.

### 3c. Frontend role-dashboard layer

```
    App.jsx (existing, mostly unchanged)
         │
         ├── existing public routes: /, /report, /complaints/:id,
         │   /impact, /community, /areas, /nearby, /login, /register
         │
         └── NEW: <ProtectedRoute> wrapper around:
                  /authority   (existing AuthorityDashboard.jsx, refined)
                  /ngo         (NEW NGODashboard.jsx)
                  /citizen     (NEW CitizenDashboard.jsx) — or reuse "/" per
                                MERGE_CONFLICTS.md §9's routing decision
                  /admin       (NEW AdminDashboard.jsx)

    Each dashboard talks ONLY to services/api.js (existing), which talks
    ONLY to FastAPI. No dashboard ever imports a Supabase client or calls
    any URL other than the existing VITE_API_BASE_URL-configured FastAPI base.
```

## 4. What is explicitly unchanged

Per the task's protected-capabilities list, the following are **inputs to** the diagram above, never touched by this merge: FastAPI itself, MongoDB + in-memory fallback, bcrypt hashing, signed-token auth, backend RBAC (`require_role`), the complaint lifecycle state machine, complaint creation, the complaint feed, community support, the AI text classifier + fallback classifier, the priority engine, SLA deadline math, media upload + privacy + EXIF handling, geolocation/nearby/areas/GeoJSON, the timeline, audit logging, notifications, rate limiting, vision-service and evidence-verification infrastructure, the backend test suite, and the ML training/evaluation structure. Every box in §2 and §3 either already exists exactly as shown, or is a strictly additive extension (new optional fields, new sibling module, new background task, new router) that no existing caller needs to know about.
