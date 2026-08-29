# ClipForge

ClipForge is an MVP that turns an uploaded long-form video or a YouTube video URL into a small set of vertical, captioned highlight clips. The source audio determines clip timing: the pipeline transcribes the source, selects transcript-backed moments near one minute, and renders 9:16 MP4 files with burned-in captions.

> Current status: the application, worker pipeline, and UI are implemented, including audio extraction and bounded ASR chunking. It is not yet a proven complete MVP: speaker auto-reframing/output quality checks are absent, and the review found material highlight-boundary, quota, and concurrency defects. See [Known limitations](docs/ARCHITECTURE.md#known-mvp-limitations) and the [code review](docs/CODE_REVIEW.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system boundaries, data flow, states, deployment, and failure behavior.
- [Codebase guide](docs/CODEBASE_GUIDE.md) — repository map, API surface, configuration, local development, and debugging.
- [Code review](docs/CODE_REVIEW.md) — findings, evidence, remediation, and readiness.
- [Product requirements](INITIAL.md) and [implementation plan](PRPs/clipforge-prp.md).

## MVP capabilities

- Email/password registration and JWT authentication.
- Project creation from a video upload or supported YouTube URL.
- Background download, transcription, highlight selection, and FFmpeg rendering.
- Selective top-N clips rather than complete source coverage.
- Target duration near 60 seconds, bounded to 40–90 seconds.
- Authenticated preview, thumbnail, download, regeneration, and deletion.
- Usage totals and free-plan limits.

Social publishing files remain in the repository, but publishing routes intentionally return “not implemented” and the pages are not mounted in the active frontend router.

## Quick start with Docker

Prerequisites: Docker with Compose and enough disk for PostgreSQL, source videos, and rendered clips.

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set `SECRET_KEY`, database credentials, and `ASR_SERVICE_API_KEY`. Then:

```powershell
docker compose up --build
```

Open `http://localhost`. The API is at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`. Uploaded and generated media is stored in the `media_data` Docker volume.

## Verification commands

Backend:

```powershell
Set-Location backend
pytest --cov=app --cov-report=term-missing --cov-fail-under=80 -q
ruff check app tests
mypy app
```

Frontend:

```powershell
Set-Location frontend
npm test
npm run lint
npm run type-check
npm run build
```

See the [review report](docs/CODE_REVIEW.md#verification) for results actually observed during the latest review.
