/**
 * Core domain types for ClipForge, mirroring the backend SQLAlchemy models
 * (backend/app/models/*.py). Enum fields are modeled as string literal
 * unions matching the backend `enum.Enum` values exactly.
 */

// ---------------------------------------------------------------------------
// User (backend/app/models/user.py)
// ---------------------------------------------------------------------------

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Project (backend/app/models/project.py)
// ---------------------------------------------------------------------------

export type SourceType = 'upload' | 'url';

export type ProjectStatus =
  | 'pending'
  | 'transcribing'
  | 'analyzing'
  | 'ready'
  | 'failed';

export interface Project {
  id: number;
  user_id: number;
  title: string;
  source_type: SourceType;
  source_url: string | null;
  source_file_path: string | null;
  duration_seconds: number | null;
  status: ProjectStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string | null;
}

// ---------------------------------------------------------------------------
// ProcessingJob (backend/app/models/processing_job.py)
// ---------------------------------------------------------------------------

export type JobType = 'transcription' | 'highlight_detection' | 'render';

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface ProcessingJob {
  id: number;
  project_id: number;
  job_type: JobType;
  status: JobStatus;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

// ---------------------------------------------------------------------------
// Clip (backend/app/models/clip.py)
// ---------------------------------------------------------------------------

export type ClipStatus = 'queued' | 'rendering' | 'ready' | 'failed';

export interface Clip {
  id: number;
  project_id: number;
  user_id: number;
  title: string;
  start_time: number;
  end_time: number;
  transcript_snippet: string | null;
  relevance_score: number | null;
  aspect_ratio: string;
  caption_style: string | null;
  status: ClipStatus;
  video_file_path: string | null;
  thumbnail_path: string | null;
  created_at: string;
  updated_at: string | null;
}

// ---------------------------------------------------------------------------
// PublishConnection (backend/app/models/publish_connection.py)
// ---------------------------------------------------------------------------

export type Platform = 'tiktok' | 'instagram' | 'youtube_shorts';

export interface PublishConnection {
  id: number;
  user_id: number;
  platform: Platform;
  account_handle: string | null;
  connected_at: string;
}

// ---------------------------------------------------------------------------
// ScheduledPost (backend/app/models/scheduled_post.py)
// ---------------------------------------------------------------------------

export type PostStatus = 'scheduled' | 'publishing' | 'published' | 'failed';

export interface ScheduledPost {
  id: number;
  clip_id: number;
  user_id: number;
  platform: Platform;
  scheduled_at: string | null;
  status: PostStatus;
  published_url: string | null;
  error_message: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// UsageRecord (backend/app/models/usage_record.py)
// ---------------------------------------------------------------------------

export interface UsageRecord {
  id: number;
  user_id: number;
  project_id: number | null;
  minutes_processed: number;
  clips_generated: number;
  recorded_at: string;
}

// ---------------------------------------------------------------------------
// PlanLimit (backend/app/models/plan_limit.py)
// ---------------------------------------------------------------------------

export type PlanType = 'free' | 'pro';

export interface PlanLimit {
  id: number;
  user_id: number;
  plan_type: PlanType;
  monthly_minutes_limit: number;
  monthly_clips_limit: number;
}

// ---------------------------------------------------------------------------
// Usage summary & history (backend GET /usage/me, GET /usage/history)
// ---------------------------------------------------------------------------

export interface UsageSummary {
  plan_type: string;
  monthly_minutes_limit: number;
  monthly_clips_limit: number;
  minutes_used_this_period: number;
  clips_used_this_period: number;
}

export interface UsageRecordEntry {
  id: number;
  project_id: number | null;
  minutes_processed: number;
  clips_generated: number;
  recorded_at: string;
}
