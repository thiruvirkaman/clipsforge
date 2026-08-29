# ClipForge Codebase Guide

This guide explains where behavior lives and how a request moves through the implemented MVP.

## Repository map

```text
.
├── backend/
│   ├── app/
│   │   ├── auth/          JWT/password helpers
│   │   ├── models/        SQLAlchemy entities
│   │   ├── routers/       FastAPI endpoints
│   │   ├── schemas/       Pydantic contracts
│   │   ├── services/      Business/provider integrations
│   │   ├── tasks/         Celery pipeline
│   │   ├── config.py      Environment settings
│   │   ├── main.py        FastAPI composition
│   │   └── storage.py     Local media abstraction
│   ├── alembic/           Migrations
│   └── tests/             pytest suite
├── frontend/src/
│   ├── components/        Feature UI
│   ├── context/           Authentication state
│   ├── hooks/             TanStack Query feature APIs
│   ├── pages/             Route screens
│   ├── services/          Axios/auth client
│   └── types/             Frontend contracts
├── docs/                  Architecture and review
├── PRPs/                  Plan, not runtime code
├── INITIAL.md             Requirements
└── docker-compose*.yml    Local stacks
```

## Backend map

`app/main.py` creates FastAPI, installs CORS/error handlers, and mounts routers under `/api/v1`. Normal flow is:

`router → authentication dependency → service → database/storage/queue`

| Service | Responsibility |
|---|---|
| `auth_service.py` | Registration, login, refresh rotation, logout |
| `project_service.py` | Upload/URL creation, probing, delete, process start |
| `youtube_service.py` | YouTube validation and yt-dlp download |
| `asr_service.py` | Timestamped ASR contract/OpenAI-compatible client |
| `highlight_service.py` | LLM or heuristic top-N selection |
| `render_service.py` | FFmpeg vertical render, SRT, thumbnail |
| `clip_service.py` | Clip reads, deletion, regeneration |
| `usage_service.py` | Plan defaults, aggregation, preflight check |
| `media_cleanup.py` | Reference-aware deletion |
| `storage.py` | Safe local paths/save/delete |

`tasks/pipeline.py` is orchestration. Read it with `Project`, `Clip`, `ProcessingJob`, and `UsageRecord` before changing pipeline semantics.

## Frontend map

`App.tsx` defines public login/register routes and protected dashboard, project, clip, profile, settings, and usage routes. `AuthContext` owns session state. `services/api.ts` attaches bearer tokens and refreshes after unauthorized responses.

`useProjects`, `useClips`, and `useUsage` connect screens to HTTP and poll only while processing is active. `useAuthenticatedMedia` fetches protected binaries and revokes browser object URLs. Publishing files are inactive scaffolding, not evidence that publishing works.

## API surface

All paths use `/api/v1`.

| Method/path | Purpose |
|---|---|
| `POST /auth/register` | Create user |
| `POST /auth/login` | Issue tokens |
| `POST /auth/refresh` | Rotate refresh token |
| `POST /auth/logout` | Revoke refresh token |
| `GET /auth/me` | Current user |
| `GET, POST /projects` | List/create projects |
| `GET, DELETE /projects/{id}` | Read/delete owned project |
| `POST /projects/{id}/process` | Enqueue pipeline |
| `GET /projects/{id}/jobs` | Job history |
| `GET /projects/{id}/clips` | Project clips |
| `GET, DELETE /clips/{id}` | Read/delete clip |
| `POST /clips/{id}/regenerate` | Re-render a window/style |
| `GET /clips/{id}/download` | Authorized MP4 |
| `GET /clips/{id}/thumbnail` | Authorized thumbnail |
| `GET /usage/me` | Plan/current totals |
| `GET /usage/history` | Usage records |

Connection/post/publish routes exist but return not implemented.

## End-to-end walkthrough

### Create

Uploads are extension/size checked, saved, ffprobed, duration-limited to three hours, and stored as pending projects. URL creation stores a supported-looking YouTube URL; the response does not prove the remote video exists.

### Start

`POST /projects/{id}/process` checks ownership, state, and current usage; clears a prior run when applicable; sets transcribing; and calls Celery `.delay()`.

### Transcribe

The worker downloads a URL source if needed, resolves its media key, and invokes `WhisperAPITranscriptionService`. The service extracts 16 kHz mono MP3; files above a 20 MB target are split by estimated duration, transcribed separately, and timestamps are shifted into source time. The join has no overlap/context, and a real long-form provider run was not verified here.

The target flow calls for metadata validation before download. Current yt-dlp code performs download while extracting metadata and only then validates duration/live state. Explicit audio extraction is implemented after ingestion.

### Select

With `LLM_SERVICE_API_KEY`, a remote LLM returns structured candidates. Otherwise the deterministic selector scans transcript windows, scores useful language, removes overlaps, and keeps up to eight. Candidates become queued clips.

### Render/finalize

Each clip renders independently. FFmpeg seeks, crops/scales/pads to 1080×1920, burns SRT captions, writes MP4, and extracts a thumbnail. When siblings terminate, any successful render makes the project ready and usage is recorded; all failures fail the project.

The crop is fixed and centered. There is no face/speaker detection, tracking, or time-varying reframe. There is also no hook/B-roll composition or post-render media/content quality gate beyond FFmpeg process success.

### Preview

The browser requests media with the access token. The API checks ownership and returns a file; the frontend creates and later revokes an object URL.

## Configuration

| Variable | Required | Notes |
|---|---:|---|
| `DATABASE_URL` | Yes | SQLAlchemy connection |
| `SECRET_KEY` | Yes | JWT signing key |
| `ASR_SERVICE_API_KEY` | For processing | Default OpenAI bearer key |
| `ASR_SERVICE_BASE_URL` | No | Defaults to `https://api.openai.com` |
| `ASR_MODEL` | No | Defaults to `whisper-1` |
| `LLM_SERVICE_API_KEY` | No | LLM selector; heuristic without it |
| `CELERY_BROKER_URL` | Deployment | Redis in Compose |
| `CELERY_RESULT_BACKEND` | Deployment | Redis DB 1 in Compose |
| `MEDIA_STORAGE_PATH` | No | Defaults `/data/media` |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins |

Compose constructs its database URL from `DB_USER`, `DB_PASSWORD`, and `DB_NAME`; keep them mutually consistent.

## Development and checks

Docker is the shortest supported path:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Backend checks:

```powershell
Set-Location backend
pytest --cov=app --cov-report=term-missing --cov-fail-under=80 -q
ruff check app tests
mypy app
```

Frontend checks:

```powershell
Set-Location frontend
npm test
npm run lint
npm run type-check
npm run build
```

Provider and FFmpeg boundaries are mocked or fixture-driven in many tests. Passing unit tests does not prove a real YouTube-to-ASR-to-render job.

## Debugging map

| Symptom | Inspect first |
|---|---|
| Stuck transcribing | Worker logs, Redis, latest processing job |
| URL fails before ASR | yt-dlp error and temporary disk space |
| ASR 400/413 | API key/model and actual generated chunk size |
| No clips | Stored segments and chosen highlight provider |
| Render failure | Render job error, source key, FFmpeg stderr |
| Media 401/404 | Refresh flow, ownership, media key/file |
| Duplicate usage | Rows per project and simultaneous completions |

## Extension points

- Add audio extraction/chunk merging or a local faster-whisper implementation behind `TranscriptionService`.
- Add an Ollama text model behind the highlight-service contract, not the ASR contract.
- Add object storage behind the storage interface before multi-host deployment.
- When changing tasks, include idempotency, transaction/dispatch boundaries, retries, and recovery—not only another `.delay()`.
