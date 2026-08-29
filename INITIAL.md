# INITIAL.md - Define Your Product

> Fill this out, then run `/generate-prp INITIAL.md`

---

## PRODUCT

**Name:** ClipForge

**Description:** Upload a long-form video (or paste a YouTube/podcast URL) and ClipForge automatically transcribes it, finds the most engaging moments, and generates ready-to-post vertical short clips (with burned-in captions) for TikTok, Instagram Reels, and YouTube Shorts. For creators, podcasters, and marketers who don't have time to manually cut clips.

**Type:** SaaS

---

## TECH STACK

| Layer | Choice |
|-------|--------|
| Backend | FastAPI + Python |
| Frontend | React + TypeScript + Vite |
| Database | PostgreSQL |
| Auth | JWT + email/password (bcrypt) |
| UI | Tailwind |
| Payments | None (usage limits tracked, no billing integration yet) |
| Background Jobs | Celery + Redis (async video processing pipeline) |

---

## MODULES

### Module 1: Authentication (Built-in)

**Models:** User, RefreshToken

**Endpoints:**
- POST /auth/register, /auth/login, /auth/refresh
- GET /auth/me

**Pages:** /login, /register, /profile

---

### Module 2: Video Projects

**Description:** A Project represents one source video a user wants turned into shorts. Source can be a direct upload or a URL (YouTube/podcast link). Tracks overall processing status.

**Models:**
```
Project:
  - id, user_id (FK)
  - title: str
  - source_type: enum(upload, url)
  - source_url: str | null
  - source_file_path: str | null
  - duration_seconds: int | null
  - status: enum(pending, transcribing, analyzing, ready, failed)
  - error_message: str | null
  - created_at, updated_at
```

**Endpoints:**
```
GET    /api/projects              - List user's projects
POST   /api/projects              - Create project (upload file or submit URL)
GET    /api/projects/{id}         - Get project detail + status
DELETE /api/projects/{id}         - Delete project (and its clips)
POST   /api/projects/{id}/process - Kick off transcription + highlight-detection pipeline (async job)
GET    /api/projects/{id}/jobs    - Poll background job status for this project
```

**Pages:**
```
/projects           - List of projects with status badges
/projects/new        - Upload file or paste URL
/projects/{id}       - Project detail: processing progress, then generated clips grid
```

---

### Module 3: Clip Generation

**Description:** Once a Project is transcribed, the highlight-detection step selects only the best moments (not full-video coverage — most of the source is never clipped): the LLM ranks candidate moments by relevance_score and keeps the top N (configurable, default ~5-10 per project). Clip boundaries target ~60s but are not a hard cap — the LLM snaps start/end to the nearest sentence/topic boundary purely from the transcript text (semantic only; no audio silence/pause detection is used), so an individual clip may run shorter or somewhat longer (roughly 40-90s) rather than being cut mid-sentence. Clips are rendered as vertical (9:16) videos with burned-in captions via ffmpeg. Processing runs as background jobs (Celery + Redis), calling out to an ASR API (e.g. Whisper) for transcription and an LLM for highlight/moment selection — pluggable behind a service interface, not hardcoded to one vendor.

**Models:**
```
ProcessingJob:
  - id, project_id (FK)
  - job_type: enum(transcription, highlight_detection, render)
  - status: enum(queued, running, completed, failed)
  - error_message: str | null
  - started_at, completed_at

Clip:
  - id, project_id (FK), user_id (FK)
  - title: str
  - start_time: float (seconds into source)
  - end_time: float
  - transcript_snippet: text
  - relevance_score: float
  - aspect_ratio: str (default "9:16")
  - caption_style: str
  - status: enum(queued, rendering, ready, failed)
  - video_file_path: str | null
  - thumbnail_path: str | null
  - created_at, updated_at
```

**Endpoints:**
```
GET    /api/projects/{id}/clips   - List generated clips for a project
GET    /api/clips/{id}            - Clip detail (preview, transcript, timestamps)
POST   /api/clips/{id}/regenerate - Re-render clip with adjusted timestamps/caption style
DELETE /api/clips/{id}            - Delete a clip
```

**Pages:**
```
/projects/{id}       - Clips grid (shared with Module 2 project detail page)
/clips/{id}          - Clip preview player, transcript, edit start/end, regenerate
```

---

### Module 4: Export & Publish

**Description:** Download finished clips, or connect a social account and publish/schedule a clip directly to it.

**Models:**
```
PublishConnection:
  - id, user_id (FK)
  - platform: enum(tiktok, instagram, youtube_shorts)
  - access_token: str (encrypted at rest)
  - refresh_token: str | null
  - account_handle: str | null
  - connected_at

ScheduledPost:
  - id, clip_id (FK), user_id (FK)
  - platform: enum(tiktok, instagram, youtube_shorts)
  - scheduled_at: datetime | null (null = publish immediately)
  - status: enum(scheduled, publishing, published, failed)
  - published_url: str | null
  - error_message: str | null
  - created_at
```

**Endpoints:**
```
GET    /api/clips/{id}/download        - Download rendered clip file
POST   /api/publish/connections/{platform} - Start OAuth connect flow for a platform
GET    /api/publish/connections        - List connected accounts
DELETE /api/publish/connections/{id}   - Disconnect an account
POST   /api/clips/{id}/publish         - Publish or schedule clip to a connected platform
GET    /api/publish/posts              - List scheduled/published posts + status
```

**Pages:**
```
/clips/{id}                 - Includes "Download" and "Publish" actions
/settings/connections        - Connect/disconnect TikTok, Instagram, YouTube Shorts
/settings/scheduled-posts    - List of scheduled/published posts
```

---

### Module 5: Usage & Billing (limits only, no payment processing)

**Description:** Track processing minutes and clips generated per user against plan limits (no Stripe integration in this MVP — just enforcement + visibility, ready to wire billing in later).

**Models:**
```
UsageRecord:
  - id, user_id (FK), project_id (FK)
  - minutes_processed: float
  - clips_generated: int
  - recorded_at

PlanLimit:
  - id, user_id (FK)
  - plan_type: enum(free, pro)
  - monthly_minutes_limit: int
  - monthly_clips_limit: int
```

**Endpoints:**
```
GET /api/usage/me       - Current period usage vs. plan limits
GET /api/usage/history   - Past usage records
```

**Pages:**
```
/settings/usage   - Usage bars/quota vs. plan limit
```

---

### Module 6: Dashboard (Built-in)

**Pages:** /dashboard (recent projects, usage summary, quick "new project" CTA), /settings (profile, connections, usage, billing placeholder)

---

## MVP SCOPE

Must Have:
- [x] User registration/login (JWT + email/password)
- [ ] Upload a video or submit a URL as a Project
- [ ] Background pipeline: transcription -> highlight detection -> vertical clip render with captions
- [ ] View generated clips per project, preview and download
- [ ] Track usage against plan limits

Nice to Have (included as stretch within Module 4):
- [ ] Connect social accounts and publish/schedule clips directly

---

## ACCEPTANCE CRITERIA

- [ ] Users can register and login (JWT + email/password)
- [ ] Users can create a Project from an upload or URL and see its processing status update
- [ ] The async pipeline produces at least one Clip with a rendered vertical video + captions per successfully processed Project
- [ ] Users can preview, download, and delete Clips
- [ ] Users can view their usage against plan limits
- [ ] 80%+ test coverage
- [ ] Docker builds successfully (including a worker service for Celery)

---

## RUN

```bash
/generate-prp INITIAL.md
/execute-prp PRPs/clipforge-prp.md
```
