export type JobStatus =
  | "queued"
  | "processing"
  | "completed"
  | "completed_with_warnings"
  | "failed_partial"
  | "failed";

export interface ArtifactManifest {
  extracted_audio?: string | null;
  normalized_audio?: string | null;
  raw_transcript?: string | null;
  segments_json?: string | null;
  words_json?: string | null;
  transcript_clean_txt?: string | null;
  transcript_clean_md?: string | null;
  final_speech_text_md?: string | null;
  transcript_clean_docx?: string | null;
  transcript_clean_pdf?: string | null;
  subtitles_srt?: string | null;
  summary_md?: string | null;
  summary_json?: string | null;
  diarization_dump?: string | null;
  log_file?: string | null;
  config_snapshot?: string | null;
}

export interface DiarizationQuality {
  detected_cluster_count_max?: number | null;
  min_centroid_similarity_margin?: number | null;
  dominant_cluster_share?: number | null;
  unmapped_segment_count?: number | null;
  speaker_switch_count?: number | null;
  total_segment_count?: number | null;
}

export interface DiarizationConfidence {
  version: number;
  mode: "reliable_labels" | "transcript_without_labels" | string;
  reason_codes: string[];
  metrics: {
    detected_cluster_count?: number | null;
    min_centroid_margin?: number | null;
    dominant_cluster_share?: number | null;
  };
  thresholds: {
    min_centroid_margin?: number | null;
    max_dominant_cluster_share?: number | null;
    min_segments_for_imbalance?: number | null;
  };
}

export interface JobMetadata {
  display_title?: string | null;
  title?: string | null;
  source_filename?: string | null;
  execution?: string | null;
  current_stage?: string | null;
  last_message?: string | null;
  progress?: number | null;
  events?: JobEvent[];
  diarization_quality?: DiarizationQuality | null;
  diarization_confidence?: DiarizationConfidence | null;
  saved_markdown_path?: string | null;
  saved_markdown_filename?: string | null;
  saved_markdown_dir?: string | null;
  saved_markdown_status?: string | null;
  saved_markdown_message?: string | null;
  saved_markdown_missing?: boolean | null;
  final_markdown_dir?: string | null;
  [key: string]: unknown;
}

export interface Job {
  job_id: string;
  source_paths: string[];
  status: JobStatus;
  detected_language?: string | null;
  artifacts: ArtifactManifest;
  metadata: JobMetadata;
  warnings: string[];
}

export type BatchItemStatus = "configure" | "processing" | "ready" | "failed";

export interface BatchSessionItem {
  item_id: string;
  position: number;
  input_path?: string | null;
  source_name: string;
  display_title: string;
  output_dir?: string | null;
  output_dir_override?: string | null;
  job_id?: string | null;
  attempt_job_ids: string[];
  status: BatchItemStatus;
  job_status?: JobStatus | null;
}

export interface BatchSession {
  session_id: string;
  created_at: string;
  common_output_dir?: string | null;
  status: "active" | "completed" | "completed_with_errors";
  totals: {
    total: number;
    configure: number;
    processing: number;
    ready: number;
    failed: number;
  };
  items: BatchSessionItem[];
}

export interface WordToken {
  segment_id?: string;
  speaker_label?: string | null;
  text: string;
  text_clean?: string | null;
  confidence?: number | null;
  issues?: WordIssue[];
  start_seconds: number;
  end_seconds: number;
}

export interface WordIssue {
  code: string;
  severity: "info" | "warning" | "error" | string;
  message: string;
}

export interface TranscriptSegment {
  segment_id: string;
  start_seconds: number;
  end_seconds: number;
  text_raw: string;
  text_clean: string;
  speaker_label?: string | null;
  words?: WordToken[];
}

export interface Artifact {
  name: string;
  filename: string;
  size_bytes: number;
  download_url: string;
}

export interface FinalMarkdownStatus {
  status: string;
  message: string;
  path?: string | null;
  filename?: string | null;
  missing?: boolean;
}

export interface TempCleanupReport {
  removed_files: string[];
  removed_count: number;
  freed_bytes: number;
  errors: string[];
}

export interface SpeakerReviewGroup {
  machine_label: string;
  fallback_label: string;
  display_label: string;
  example: string;
  suggestions: string[];
}

export interface SpeakerReviewPayload {
  status: "pending" | "confirmed" | "skipped" | "not_required" | string;
  groups: SpeakerReviewGroup[];
  suggestions: string[];
}

export interface JobEvent {
  timestamp: string;
  stage: string;
  status: "ok" | "warning" | "error" | string;
  message: string;
  progress: number;
}

export interface ModelStatus {
  name: string;
  label?: string;
  backend?: string;
  language?: string;
  description?: string;
  status: "ready" | "missing" | "corrupt" | "queued" | "downloading" | "error" | "unknown" | string;
  path?: string;
  size_bytes?: number;
  downloaded_bytes?: number;
  total_bytes?: number | null;
  progress?: number;
  message?: string;
  updated_at?: string;
  stale_download?: boolean;
}

export interface ModelsPayload {
  current_model: string;
  models: ModelStatus[];
}

export interface MediaToolStatus {
  available: boolean;
  path?: string | null;
}

export interface HealthPayload {
  status: string;
  app?: {
    output_dir: string;
    temp_dir: string;
    cache_dir: string;
    model_dir?: string | null;
  };
  media_tools?: {
    ffmpeg: MediaToolStatus;
    ffprobe: MediaToolStatus;
  };
}

export interface AppEnvironment {
  apiBaseUrl: string;
  backendLifecycle?: BackendLifecycle | null;
  defaultModelName?: string | null;
  autosaveMarkdownDir?: string | null;
  appDataDir?: string | null;
  cacheDir?: string | null;
  modelDir?: string | null;
  outputDir?: string | null;
  ffmpegAvailable?: boolean;
  ffprobeAvailable?: boolean;
  ffmpegPath?: string | null;
  ffprobePath?: string | null;
  desktopPlatform?: "macos" | "windows" | "unsupported";
  nativeFileActions?: boolean;
  isTauri: boolean;
}

export type BackendLifecycleState =
  | "starting"
  | "checking"
  | "online"
  | "offline"
  | "error"
  | "restarting"
  | string;

export interface BackendLifecycle {
  state: BackendLifecycleState;
  human_message: string;
  technical_detail?: string | null;
  last_check_at?: string | null;
  recent_output: string[];
}
