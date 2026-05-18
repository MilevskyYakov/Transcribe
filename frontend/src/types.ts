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

export interface Job {
  job_id: string;
  source_paths: string[];
  status: JobStatus;
  detected_language?: string | null;
  artifacts: ArtifactManifest;
  metadata: Record<string, unknown>;
  warnings: string[];
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
  status: "ready" | "missing" | "corrupt" | "downloading" | "error" | "unknown" | string;
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
  };
  media_tools?: {
    ffmpeg: MediaToolStatus;
    ffprobe: MediaToolStatus;
  };
}

export interface AppEnvironment {
  apiBaseUrl: string;
  defaultModelName?: string | null;
  appDataDir?: string | null;
  cacheDir?: string | null;
  outputDir?: string | null;
  ffmpegAvailable?: boolean;
  ffprobeAvailable?: boolean;
  ffmpegPath?: string | null;
  ffprobePath?: string | null;
  isTauri: boolean;
}
