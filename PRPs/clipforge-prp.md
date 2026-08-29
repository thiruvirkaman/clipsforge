# PRP: ClipForge

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | ClipForge |
| **Type** | SaaS |
| **Version** | 1.1 |
| **Created** | 2026-08-29 |
| **Complexity** | High |

---

## PRODUCT OVERVIEW

**Description:** Upload a long-form video (or paste a YouTube/podcast URL) and ClipForge automatically transcribes it, finds the most engaging moments, and generates ready-to-post vertical short clips (with burned-in captions) for TikTok, Instagram Reels, and YouTube Shorts.

**Value Proposition:** Creators, podcasters, and marketers spend hours manually finding and cutting highlight moments from long recordings. ClipForge automates transcription, highlight detection, vertical reformatting, and captioning, turning one long video into a batch of postable shorts in minutes.

**MVP Scope:**
- [ ] User registration/login (JWT + email/password)
- [ ] Create a Project from an uploaded file or a source URL
- [ ] Async pipeline: transcription -> highlight detection -> vertical render with captions
- [ ] Preview, download, and delete generated Clips
- [ ] Usage tracked against plan limits
- [ ] (Stretch) Connect social accounts and publish/schedule Clips

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+ | skills/BACKEND.md |
| Frontend | React + TypeScript + Vite | skills/FRONTEND.md |
| Database | PostgreSQL + SQLAlchemy | skills/DATABASE.md |
| Auth | JWT + bcrypt (email/password) | skills/BACKEND.md |
| UI | Tailwind | skills/FRONTEND.md |
| Background Jobs | Celery + Redis | skills/BACKEND.md |
| Media Processing | ffmpeg (render), pluggable ASR service (transcription), pluggable LLM service (highlight detection) | skills/BACKEND.md |
| Testing | pytest + RTL | skills/TESTING.md |
| Deployment | Docker + GitHub Actions (adds a `worker` service for Celery) | skills/DEPLOYMENT.md |

---

## DATABASE MODELS

### User
- id, email, hashed_password, full_name, is_active, is_verified, created_at

### RefreshToken
- id, user_id (FK), token, expires_at, created_at, revoked

### Project
- id, user_id (FK), title, source_type (upload | url), source_url, source_file_path, duration_seconds, status (pending | transcribing | analyzing | ready | failed), error_message, created_at, updated_at

### ProcessingJob
- id, project_id (FK), job_type (transcription | highlight_detection | render), status (queued | running | completed | failed), error_message, started_at, completed_at

### Clip
- id, project_id (FK), user_id (FK), title, start_time (float), end_time (float), transcript_snippet, relevance_score (float), aspect_ratio (default "9:16"), caption_style, status (queued | rendering | ready | failed), video_file_path, thumbnail_path, created_at, updated_at
- **Selection & duration rule:** only the top N (default ~5-10, configurable) highest-`relevance_score` moments per Project become Clip rows — the source video is never divided end-to-end. `start_time`/`end_time` target ~60s apart but are not clamped to it; they snap to the nearest sentence/topic boundary in the transcript text (semantic only, no audio silence/pause detection), so real durations land roughly in the 40-90s range.

### PublishConnection
- id, user_id (FK), platform (tiktok | instagram | youtube_shorts), access_token (encrypted), refresh_token, account_handle, connected_at

### ScheduledPost
- id, clip_id (FK), user_id (FK), platform, scheduled_at (nullable = publish now), status (scheduled | publishing | published | failed), published_url, error_message, created_at

### UsageRecord
- id, user_id (FK), project_id (FK), minutes_processed (float), clips_generated (int), recorded_at

### PlanLimit
- id, user_id (FK), plan_type (free | pro), monthly_minutes_limit (int), monthly_clips_limit (int)

**Relationships:** User 1—N Project; Project 1—N ProcessingJob; Project 1—N Clip; User 1—N PublishConnection; Clip 1—N ScheduledPost; User 1—N UsageRecord; User 1—1 PlanLimit.

---

## MODULES

### Module 1: Authentication
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|--------------|
| POST | /auth/register | Create account |
| POST | /auth/login | Get tokens |
| POST | /auth/refresh | Refresh token |
| GET | /auth/me | Current user |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /login | LoginPage | LoginForm |
| /register | RegisterPage | RegisterForm |
| /profile | ProfilePage | ProfileForm |

---

### Module 2: Video Projects
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | /api/projects | List user's projects |
| POST | /api/projects | Create project (upload file or submit URL) |
| GET | /api/projects/{id} | Get project detail + status |
| DELETE | /api/projects/{id} | Delete project and its clips |
| POST | /api/projects/{id}/process | Kick off transcription + highlight-detection pipeline |
| GET | /api/projects/{id}/jobs | Poll background job status |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /projects | ProjectsListPage | ProjectCard, StatusBadge |
| /projects/new | NewProjectPage | UploadDropzone, UrlInputForm |
| /projects/{id} | ProjectDetailPage | ProcessingProgress, ClipsGrid |

---

### Module 3: Clip Generation
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | /api/projects/{id}/clips | List generated clips for a project |
| GET | /api/clips/{id} | Clip detail (preview, transcript, timestamps) |
| POST | /api/clips/{id}/regenerate | Re-render clip with adjusted timestamps/caption style |
| DELETE | /api/clips/{id} | Delete a clip |

**Backend Services (Celery tasks):**
| Task | Description |
|------|--------------|
| `transcribe_project` | Calls pluggable ASR service, stores timestamped transcript, updates ProcessingJob |
| `detect_highlights` | Calls pluggable LLM service on the transcript; ranks candidate moments by relevance and keeps only the top N (default ~5-10) — not full-video coverage. For each kept moment, sets `start_time`/`end_time` by snapping to the nearest sentence/topic boundary **in the transcript text** (semantic only — no acoustic/silence detection), targeting ~60s as a soft goal, never a hard cutoff (real range ~40-90s). Creates candidate Clip rows. |
| `render_clip` | ffmpeg: crop to 9:16, burn in captions, generate thumbnail |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /projects/{id} | (shared) | ClipsGrid, ClipCard |
| /clips/{id} | ClipDetailPage | ClipPlayer, TranscriptPanel, TrimControls, RegenerateButton |

---

### Module 4: Export & Publish
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | /api/clips/{id}/download | Download rendered clip file |
| POST | /api/publish/connections/{platform} | Start OAuth connect flow |
| GET | /api/publish/connections | List connected accounts |
| DELETE | /api/publish/connections/{id} | Disconnect an account |
| POST | /api/clips/{id}/publish | Publish or schedule clip to a platform |
| GET | /api/publish/posts | List scheduled/published posts |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /settings/connections | ConnectionsPage | PlatformConnectCard |
| /settings/scheduled-posts | ScheduledPostsPage | PostStatusTable |

---

### Module 5: Usage & Billing (limits only)
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Description |
|--------|----------|--------------|
| GET | /api/usage/me | Current period usage vs. plan limits |
| GET | /api/usage/history | Past usage records |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /settings/usage | UsagePage | UsageBar, PlanLimitCard |

---

### Module 6: Dashboard
**Agents:** FRONTEND-AGENT

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /dashboard | DashboardPage | RecentProjects, UsageSummary, NewProjectCTA |
| /settings | SettingsLayout | nav to profile/connections/usage |

---

## PHASE EXECUTION PLAN

**Phase 1: Foundation (4 agents in parallel)**
- DATABASE-AGENT: All models (User, RefreshToken, Project, ProcessingJob, Clip, PublishConnection, ScheduledPost, UsageRecord, PlanLimit), migrations, database.py
- BACKEND-AGENT: main.py, config.py, project structure, Celery app + Redis config, storage abstraction for uploaded/rendered media
- FRONTEND-AGENT: Vite setup, folder structure, base components, Tailwind config
- DEVOPS-AGENT: Docker (api + worker + redis + postgres services), CI/CD, env files

**Validation Gate 1:** pip install, alembic upgrade, npm install, docker-compose config

**Phase 2: Modules (backend + frontend parallel per module)**
- Auth Module: JWT email/password endpoints + Login/Register/Profile pages
- Video Projects Module: upload/URL intake API + Projects list/new/detail pages
- Clip Generation Module: Celery pipeline (transcribe -> select top-N highlights with semantic boundary snapping -> render) + Clip detail/preview pages
- Export & Publish Module: download + OAuth connect + publish/schedule endpoints + Connections/Scheduled Posts pages
- Usage & Billing Module: usage tracking endpoints + Usage page
- Dashboard Module: dashboard + settings shell

**Validation Gate 2:** ruff check, mypy, npm lint, npm type-check

**Phase 3: Quality (3 agents in parallel)**
- TEST-AGENT: pytest (incl. mocked ASR/LLM/ffmpeg calls in Celery task tests, and unit tests asserting `detect_highlights` keeps only top-N and never clamps duration at exactly 60s) + RTL tests, 80%+ coverage
- REVIEW-AGENT: Security audit (signed URLs for media downloads, encrypted PublishConnection tokens, upload size/type validation), performance review
- RESEARCH-AGENT: Best practices validation for async video pipelines

**Final Validation:** Full test suite, docker build (api + worker + redis + postgres), health checks

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `alembic upgrade head`, `npm install`, `docker-compose config` |
| 2 | `ruff check backend/`, `npm run type-check` |
| 3 | `pytest --cov --cov-fail-under=80`, `npm test` |
| Final | `docker-compose up -d`, `curl localhost:8000/health` |

---

## ENVIRONMENT VARIABLES

```env
DATABASE_URL=postgresql://user:password@localhost:5432/clipforge
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
VITE_API_URL=http://localhost:8000

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

ASR_SERVICE_API_KEY=your-asr-provider-key
ASR_SERVICE_BASE_URL=https://api.your-asr-provider.com
LLM_SERVICE_API_KEY=your-llm-provider-key

MEDIA_STORAGE_PATH=/data/media
MEDIA_STORAGE_BACKEND=local

TIKTOK_CLIENT_ID=xxx
TIKTOK_CLIENT_SECRET=xxx
INSTAGRAM_CLIENT_ID=xxx
INSTAGRAM_CLIENT_SECRET=xxx
YOUTUBE_CLIENT_ID=xxx
YOUTUBE_CLIENT_SECRET=xxx
```

---

## NEXT STEP

Execute with parallel agents:
/execute-prp PRPs/clipforge-prp.md
