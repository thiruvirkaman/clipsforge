# ClipForge MVP Code Review

Review date: 2026-08-29

## Executive result

**NOT READY TO COMMIT as the supplied target MVP.** The upload/YouTube → extracted/chunked transcript → highlights → render flow exists. However, speaker auto-reframing and an output quality gate are absent, and material boundary-selection, quota, and concurrency/idempotency defects remain. No real long-form external-provider E2E run was verified.

MVP scope is respected: local storage, one worker tier, polling, heuristic fallback, and disabled publishing are acceptable simplifications. Findings focus on required behavior or state, usage, and credential risk.

## Scope and evidence

Reviewed requirements and plan, backend routers/services/models/tasks/migrations/tests, frontend routes/hooks/API/tests, Docker/nginx, and CI. Provider behavior was checked against OpenAI's official [speech-to-text guide](https://developers.openai.com/api/docs/guides/speech-to-text): uploads are limited to 25 MB; segment timestamp granularity is available with `whisper-1`.

The review also uses the supplied target sequence: metadata → download → audio extraction → timestamped transcript → full-transcript analysis → candidate ranking → source cut → vertical reframe → captions → optional enrichment → quality check → MP4.

## Findings

### MAJOR — Punctuation-free transcripts collapse to one clip

**Location:** `backend/app/services/highlight_service.py:68-110,145-168`.

**Risk/requirement:** Selection should produce useful concept clips at transcript boundaries. Boundary candidates always include the first segment, so the fallback to all starts never runs when terminal punctuation is absent.

**Failure:** Short unpunctuated ASR segments make every scan snap to time zero; overlap de-duplication leaves one clip for a long source.

**Evidence:** A deterministic probe with 75 eight-second punctuation-free segments returned one `(0, 56)` window.

**Remediation:** Treat only-the-first boundary as no useful sentence boundaries and fall back to segment/topic starts. Add a regression expecting multiple non-overlapping candidates.

### MAJOR — ASR chunk joins can lose speech context at boundaries

**Location:** `backend/app/services/asr_service.py:160-199`.

**Risk/requirement:** Long-form concepts depend on a complete timestamped transcript. Chunks use equal time intervals with stream copy and are concatenated without overlap, context prompt, or boundary de-duplication.

**Failure:** Speech crossing a cut can be truncated or decoded inconsistently, degrading transcript content around a possible highlight boundary. An unexpectedly large encoded chunk is also not rechecked before upload.

**Evidence:** Each chunk starts exactly at the prior duration boundary; segments are directly extended and text directly joined. `_transcribe_file` is called without checking generated chunk size.

**Remediation:** Add overlap, preceding-text context where supported, and overlap de-duplication; assert every generated file is below the hard provider limit. Cover boundaries and one real long-form run.

### MAJOR — LLM candidates bypass semantic boundary snapping

**Location:** `backend/app/services/highlight_service.py:196-252`.

**Risk/requirement:** Concepts must end near sentence/topic boundaries and not mid-speech. LLM timestamps are clamped to bounds/duration only, not transcript segments.

**Failure:** A candidate `12.3–115` becomes `12.3–102.3`, an arbitrary mid-sentence cut.

**Evidence:** Normalization receives source duration, not transcript boundaries, and hard-caps `start + MAX_CLIP_SECONDS`.

**Remediation:** Snap every provider candidate to valid transcript start/end boundaries within 40–90 seconds, rebuild its snippet, then validate overlap.

### MAJOR — Processing start is not concurrency-safe

**Location:** `backend/app/services/project_service.py:199-234`; `backend/app/services/usage_service.py:31-57,95-111`.

**Risk/requirement:** One process request should enqueue one run. `start_processing` locks the row, but nested helpers commit, ending the transaction and releasing the lock early.

**Failure:** Simultaneous requests both pass status validation and enqueue transcription, producing competing jobs/clips/cleanup.

**Evidence:** Plan initialization and previous-run usage deletion commit within the lock-owning flow.

**Remediation:** Make participating helpers flush-only and own one transaction in `start_processing`. Add a run ID/idempotency key and recoverable queue dispatch/outbox.

### MAJOR — Regeneration can stay queued or render concurrently

**Location:** `backend/app/services/clip_service.py:87-120`.

**Risk/requirement:** Regeneration needs one safe attempt. Code commits `queued` before publishing and neither handles broker failure nor rejects an active clip.

**Failure:** Redis failure leaves queued forever; repeated requests launch FFmpeg writers against the same `clip_{id}.mp4`.

**Evidence:** State commits before `.delay()` with no dispatch guard/recovery.

**Remediation:** Be idempotent for queued/rendering clips, render attempts to unique temporary files, atomically replace on success, and reconcile failed dispatch.

### MAJOR — Usage “exactly once” is a race

**Location:** `backend/app/tasks/pipeline.py:348-397`; `backend/app/models/usage_record.py:20-22`.

**Risk/requirement:** Concurrent final renders must not double-charge. Tasks can both observe no usage row; `project_id` is indexed but not unique.

**Failure:** Two last renders finish together and insert two records for one project.

**Evidence:** Separate check then insert; schema permits duplicates.

**Remediation:** Add a unique accounting key (`project_id`, or `project_id + run_id` if reruns bill separately) and conflict-safe insertion in the finalization transaction.

### MAJOR — Accepted jobs can exceed quota

**Location:** `backend/app/services/usage_service.py:128-146`; `backend/app/services/project_service.py:223-224`.

**Risk/requirement:** Usage limits are acceptance criteria. Check uses only historical totals and does not include/reserve requested work.

**Failure:** At 59/60 minutes, a user starts a three-hour source and finishes at 239 minutes; concurrent jobs overshoot further.

**Evidence:** The function receives no requested duration/clip count.

**Remediation:** Enforce `used + requested <= limit`, define unknown URL-duration policy, reserve transactionally, and reconcile actual completion/failure.

### MAJOR — Refresh bearer tokens are stored in recoverable form

**Location:** `backend/app/models/refresh_token.py:20`; `backend/app/services/auth_service.py:76-88,123-124`.

**Risk:** A database read leak exposes active login credentials. Full refresh JWTs are stored and queried verbatim.

**Failure:** An attacker submits a leaked, unexpired row to `/auth/refresh` and takes over the account.

**Evidence:** `RefreshToken.token` contains the returned JWT.

**Remediation:** Store SHA-256/HMAC token hashes or only random `jti` metadata; compare derived identifiers and rotate atomically.

### MAJOR — YouTube validation and cleanup are incomplete

**Location:** `backend/app/services/youtube_service.py:21-53,69-125`.

**Risk/requirement:** Accept actual supported video URLs and clean temporary media. Host/nonempty-path validation admits channels; duration/live checks occur after download; temp cleanup is caller-owned only after success.

**Failure:** A channel URL becomes a project then fails in the worker; failed/too-long downloads leave large temporary files.

**Evidence:** Direct validation accepted `https://www.youtube.com/@openai` and `https://youtu.be/not-a-video`.

**Remediation:** Parse watch/shorts/youtu.be video-ID shapes, inspect metadata before download, and own temp cleanup in a downloader `finally`.

### MAJOR — Target auto-reframe and output quality gate are absent

**Location:** `backend/app/services/render_service.py:95-173`; `backend/app/tasks/pipeline.py:290-309`.

**Risk/requirement:** The supplied target pipeline requires speaker tracking/reframing and a quality check before export. Rendering currently uses a static centered crop and accepts FFmpeg exit success as completion.

**Failure:** An off-center or moving speaker is cropped out, yet the clip is marked ready. A technically generated MP4 can have missing audio, wrong effective duration, unreadable captions, or no visible subject without being rejected.

**Evidence:** The FFmpeg filter uses fixed crop/scale/pad expressions; there is no detection/tracking data, post-render ffprobe validation, frame/content check, or QC state/job.

**Remediation:** First define the MVP QC contract (at least decodable MP4, 1080×1920, expected duration tolerance, audio stream, nonempty file, thumbnail). Add ffprobe-based automated checks before `ready`. If auto-track is mandatory for MVP, introduce face/person tracking that emits a time-varying crop path and define multi-speaker/no-face fallback; otherwise explicitly defer it and label the current output “center-cropped,” not “auto-reframed.”

### MINOR — Optional hook/text/B-roll stage is absent

**Location:** `backend/app/services/render_service.py`; no composition/enrichment service exists.

**Risk/requirement:** The supplied flow includes hook/text/B-roll “if needed,” but no rule defines when it is needed and code only renders captions.

**Failure:** Product/UI claims enriched shorts while exports contain only cropped source plus captions.

**Remediation:** For MVP, document caption-only output and do not claim enrichment. If retained as a requirement, define deterministic trigger, assets/licensing, layout, and fallback before implementation.

### MINOR — Missing ASR key produces no job audit row

**Location:** `backend/app/tasks/pipeline.py:48-60,102-106`.

**Risk:** Job history should explain failures. Provider preflight runs before `ProcessingJob` construction.

**Failure/evidence:** Project fails, but `job` remains `None` and `_fail_job` no-ops.

**Remediation:** Create the job before preflight or record a preflight failure job.

### MINOR — Transient worker errors are terminal

**Location:** `backend/app/tasks/pipeline.py:102-108,218-224,311-324`; `backend/app/celery_app.py`.

**Risk:** YouTube, ASR, Redis, and FFmpeg can fail transiently. Tasks catch exceptions and return, with no retry, time limit, or stale-state reconciler.

**Failure:** Brief provider failure permanently fails a project; a lost message leaves active state forever.

**Remediation:** Add bounded backoff for classified transient errors, time limits, attempt-aware idempotency, and a simple stale-job reconciliation command.

### MINOR — Provider integration still lacks full boundary evidence

**Location:** `backend/tests/test_asr_service.py`; no dedicated YouTube service suite.

**Risk/evidence:** ASR extraction/chunk offsets now have focused mocked tests, but URL parsing/cleanup lacks a dedicated suite and ASR tests do not execute FFmpeg or a real provider.

**Remediation:** Add service contract tests for validation, cleanup on all exceptions, request/response parsing, chunking/offsets, and provider failures.

## Proportionate MVP choices

- Modular monolith plus one Celery worker tier is appropriate.
- Polling and PostgreSQL/Redis are sufficient at current unmeasured scale.
- Local shared media storage is suitable for single-host Docker.
- Heuristic selection is useful once its boundary bug is fixed.
- Disabled publishing is preferable to simulated success.
- Ready-on-at-least-one-render is a reasonable partial-success policy.

## Verification

Executed against the current working tree:

- Backend in rebuilt Python 3.11 Docker image: `125 passed`, total coverage `90.57%`; Ruff passed; mypy passed for 50 source files.
- Frontend: `57 passed`; ESLint passed; TypeScript no-emit check passed; Vite production build passed (532 modules).
- Docker API image build passed. Compose warned that its top-level `version: '3.8'` is obsolete.
- Deterministic highlight probe: 75 unpunctuated eight-second segments produced only one `(0, 56)` candidate.
- URL probe: both `https://www.youtube.com/@openai` and `https://youtu.be/not-a-video` were accepted by the syntactic validator.

Not verified: a live external ASR request, a complete real upload pipeline, a complete real YouTube pipeline, speaker tracking (not implemented), output quality validation (not implemented), or production deployment.

## Pre-commit gate

| Area | Status | Evidence |
|---|---|---|
| Requirement | FAIL | Target auto-reframe and output QC are absent |
| Architecture/contracts | FAIL | Boundary/idempotency defects remain |
| Code quality | PASS | Ruff and mypy completed successfully |
| Security/data integrity | FAIL | Raw refresh tokens and usage races |
| Tests | PASS | Backend 125/125 at 90.57%; frontend 57/57 |
| Build/type/lint | PASS | API image, frontend build, Ruff, mypy, ESLint, TypeScript |
| Git diff/status | PASS | Reviewed; implementation is largely untracked and includes existing user changes |
| Overall | **NOT READY TO COMMIT** | Required target gaps and major findings remain |

## Fix order

1. Define/implement minimum post-render QC and confirm/implement target auto-tracking.
2. Harden chunk boundaries and complete one real long-form proof.
3. Transcript boundary normalization for heuristic and LLM candidates.
4. Idempotent process/regeneration/finalization with database enforcement.
5. Usage reservation/enforcement.
6. YouTube validation/cleanup and hashed refresh credentials.
7. Focused boundary tests plus real upload and YouTube smoke tests.
