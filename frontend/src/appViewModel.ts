import { formatBytes } from "./format";
import type { Artifact, BackendLifecycle, Job, JobEvent, ModelStatus, TranscriptSegment } from "./types";

export interface SpeakerTurn {
  id: string;
  speakerLabel: string;
  start_seconds: number;
  end_seconds: number;
  texts: string[];
  segments: TranscriptSegment[];
}

export const DEFAULT_API_BASE = "http://127.0.0.1:8765";

const STATUS_LABELS: Record<string, string> = {
  queued: "В очереди",
  processing: "Обработка",
  completed: "Готово",
  completed_with_warnings: "Готово с предупреждениями",
  failed_partial: "Частичная ошибка",
  failed: "Ошибка"
};

const ARTIFACT_LABELS: Record<string, string> = {
  final_speech_text_md: "Готовый текст",
  transcript_clean_md: "Транскрипт Markdown",
  transcript_clean_txt: "Транскрипт TXT",
  transcript_clean_docx: "Транскрипт DOCX",
  transcript_clean_pdf: "Транскрипт PDF",
  subtitles_srt: "Субтитры SRT",
  summary_md: "Summary",
  summary_json: "Summary JSON",
  segments_json: "Сегменты JSON",
  words_json: "Слова JSON",
  raw_transcript: "Сырой транскрипт",
  diarization_dump: "Diarization dump",
  log_file: "Лог задачи",
  config_snapshot: "Конфиг"
};

const DIARIZATION_QUALITY_WARNING_PREFIX = "Diarization quality warning:";

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function backendLifecycleLabel(lifecycle: BackendLifecycle | null | undefined): string {
  if (!lifecycle) return "Проверяем…";
  const labels: Record<string, string> = {
    starting: "Запускаем…",
    checking: "Проверяем…",
    online: "Готово",
    offline: "Проверяем…",
    error: "Не удалось запустить",
    restarting: "Перезапускаем…"
  };
  return labels[lifecycle.state] ?? lifecycle.human_message ?? lifecycle.state;
}

export function backendLifecycleTone(lifecycle: BackendLifecycle | null | undefined): string {
  if (!lifecycle) return "checking";
  if (lifecycle.state === "online") return "ok";
  if (lifecycle.state === "error") return "error";
  if (lifecycle.state === "offline") return "warn";
  return "checking";
}

export function isDiarizationQualityWarning(value: string): boolean {
  return value.startsWith(DIARIZATION_QUALITY_WARNING_PREFIX);
}

export function hasOnlyDiarizationQualityWarnings(job: Job | null): boolean {
  return (
    job?.status === "completed_with_warnings" &&
    job.warnings.length > 0 &&
    job.warnings.every(isDiarizationQualityWarning)
  );
}

export function displayStatus(job: Job): string {
  return hasOnlyDiarizationQualityWarnings(job) ? "completed" : job.status;
}

export function displayWarnings(job: Job): string[] {
  return job.warnings.filter((warning) => !isDiarizationQualityWarning(warning));
}

export function currentProgress(job: Job | null): number {
  const value = job?.metadata?.progress;
  return typeof value === "number" ? Math.max(0, Math.min(100, value)) : 0;
}

export function isFailedJob(job: Job | null): boolean {
  return job?.status === "failed" || job?.status === "failed_partial";
}

export function currentMessage(job: Job | null): string {
  if (isFailedJob(job)) return "Обработка остановилась с ошибкой";
  if (hasOnlyDiarizationQualityWarnings(job)) return "Задача успешно завершена";
  const value = job?.metadata?.last_message;
  return typeof value === "string" ? value : "Ожидание событий";
}

export function currentProgressLabel(job: Job | null): string {
  const progress = currentProgress(job);
  if (isFailedJob(job)) return `остановилось на ${progress}%`;
  return `${progress}%`;
}

export function isActiveJob(job: Job | null): boolean {
  return job?.status === "queued" || job?.status === "processing";
}

export function languageLabel(job: Job): string {
  if (job.detected_language) return `язык: ${job.detected_language}`;
  if (isActiveJob(job)) return "язык появится после распознавания";
  return "язык не определён";
}

export function titleFromFilename(filename: string): string {
  const basename = filename.split(/[\\/]/).pop() ?? filename;
  const dotIndex = basename.lastIndexOf(".");
  return dotIndex > 0 ? basename.slice(0, dotIndex) : basename;
}

export function titleValidationMessage(title: string): string | null {
  return title.trim() ? null : "Введите название транскрипции";
}

export function canSubmitTranscriptionJob(options: {
  hasMedia: boolean;
  transcriptionTitle: string;
  isSubmitting: boolean;
  selectedModelIsReady: boolean;
}): boolean {
  return (
    options.hasMedia &&
    !options.isSubmitting &&
    options.selectedModelIsReady &&
    titleValidationMessage(options.transcriptionTitle) === null
  );
}

export function jobDisplayTitle(job: Job): string {
  const metadataTitle = job.metadata?.display_title ?? job.metadata?.title;
  if (typeof metadataTitle === "string" && metadataTitle.trim()) return metadataTitle.trim();
  const sourceFilename = job.metadata?.source_filename;
  if (typeof sourceFilename === "string" && sourceFilename.trim()) {
    return titleFromFilename(sourceFilename.trim());
  }
  const firstSource = job.source_paths[0];
  if (firstSource) return titleFromFilename(firstSource);
  return job.job_id;
}

export function lastEventTime(events: JobEvent[]): number | null {
  const lastEvent = events[events.length - 1];
  if (!lastEvent) return null;
  const value = Date.parse(lastEvent.timestamp);
  return Number.isNaN(value) ? null : value;
}

export function elapsedText(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  if (seconds < 60) return `${seconds} сек`;
  return `${Math.floor(seconds / 60)} мин`;
}

export function modelLabel(model: ModelStatus): string {
  const labels: Record<string, string> = {
    ready: "Готова",
    missing: "Не скачана",
    corrupt: "Повреждена",
    queued: "В очереди",
    downloading: "Скачивается",
    error: "Ошибка",
    unknown: "Неизвестна"
  };
  return labels[model.status] ?? model.status;
}

export function modelDetail(model: ModelStatus): string {
  if (model.status === "downloading") {
    const total = model.total_bytes ? formatBytes(model.total_bytes) : "размер уточняется";
    return `${model.progress ?? 0}% · ${formatBytes(model.downloaded_bytes ?? 0)} из ${total}`;
  }
  if (model.status === "queued") return model.message ?? "Ожидает очереди";
  if (model.size_bytes) return formatBytes(model.size_bytes);
  return model.message ?? model.description ?? "";
}

export function canChooseModelAsDefault(model: ModelStatus | null): boolean {
  return model?.status === "ready";
}

export function defaultModelActionLabel(model: ModelStatus, selectedModelName: string): string {
  if (model.name === selectedModelName && canChooseModelAsDefault(model)) return "Выбрана";
  if (canChooseModelAsDefault(model)) return "По умолчанию";
  if (model.status === "downloading" || model.status === "queued") return "Скачивается";
  return "Сначала скачать";
}

export function modelDownloadActionLabel(model: ModelStatus): string {
  if (model.stale_download || model.status === "error" || model.status === "corrupt") {
    return "Скачать заново";
  }
  if (model.status === "downloading" || model.status === "queued") return "Повторить";
  return "Скачать";
}

export function canStartWithDefaultModel(model: ModelStatus | null): boolean {
  return model?.status === "ready";
}

export function selectedJobDetailsRefreshKey(job: Job | null): string {
  if (!job) return "";
  return [
    job.job_id,
    job.status,
    String(job.metadata?.current_stage ?? ""),
    String(job.metadata?.progress ?? "")
  ].join(":");
}

export function isRawRuntimeDetail(value: string): boolean {
  return (
    value.includes("ONNXRuntimeError") ||
    value.includes("CoreMLExecutionProvider") ||
    value.includes("Traceback") ||
    value.includes("ExecutionProvider")
  );
}

export function eventMessageForTest(event: JobEvent): string {
  if (event.status === "error" && isRawRuntimeDetail(event.message)) {
    return "Обработка остановилась с ошибкой";
  }
  return event.message;
}

export function eventDisplayStatus(event: JobEvent, job: Job | null): string {
  if (hasOnlyDiarizationQualityWarnings(job) && event.stage === "done" && event.status === "warning") {
    return "ok";
  }
  return event.status;
}

export function eventDisplayMessage(event: JobEvent, job: Job | null): string {
  if (hasOnlyDiarizationQualityWarnings(job) && event.stage === "done" && event.status === "warning") {
    return "Задача успешно завершена";
  }
  return eventMessageForTest(event);
}

export function speakerTurns(segments: TranscriptSegment[]): SpeakerTurn[] {
  const turns: SpeakerTurn[] = [];
  for (const segment of segments) {
    const speakerLabel = displaySpeakerLabel(segment.speaker_label);
    const text = (segment.text_clean || segment.text_raw).trim();
    const previous = turns[turns.length - 1];
    if (previous && previous.speakerLabel === speakerLabel) {
      previous.end_seconds = segment.end_seconds;
      if (text) previous.texts.push(text);
      previous.segments.push(segment);
      continue;
    }
    turns.push({
      id: segment.segment_id,
      speakerLabel,
      start_seconds: segment.start_seconds,
      end_seconds: segment.end_seconds,
      texts: text ? [text] : [],
      segments: [segment]
    });
  }
  return turns;
}

export function displaySpeakerLabel(value: string | null | undefined): string {
  const label = value?.trim();
  if (!label) return "Спикер";
  if (!label.startsWith("SPEAKER_")) return label;
  const suffix = label.slice("SPEAKER_".length);
  return /^\d+$/.test(suffix) ? `Спикер ${Number(suffix) + 1}` : "Спикер";
}

export function diarizationDiagnostic(job: Job | null): string | null {
  const quality = job?.metadata?.diarization_quality;
  if (!quality) return null;

  const detectedClusterCount = quality.detected_cluster_count_max;
  if (typeof detectedClusterCount === "number" && detectedClusterCount < 2) {
    return "Диаризация: система видит одного устойчивого спикера. Если ролей больше, проверьте подсказку участников.";
  }

  const minMargin = quality.min_centroid_similarity_margin;
  if (typeof minMargin === "number" && minMargin < 0.1) {
    return `Диаризация: роли различаются неуверенно (margin ${minMargin.toFixed(2)}), поэтому подписи спикеров стоит проверить.`;
  }

  const dominantShare = quality.dominant_cluster_share;
  if (typeof dominantShare === "number" && dominantShare >= 0.8) {
    return `Диаризация: ${Math.round(dominantShare * 100)}% сегментов отнесено к одному спикеру. Это диагностический сигнал, не ошибка обработки.`;
  }

  return "Диаризация: диагностические метрики сохранены, критичных предупреждений нет.";
}

export function artifactDisplayName(artifact: Artifact): string {
  return ARTIFACT_LABELS[artifact.name] ?? artifact.filename ?? artifact.name;
}

export function compareArtifactsForDisplay(left: Artifact, right: Artifact): number {
  if (left.name === "final_speech_text_md") return -1;
  if (right.name === "final_speech_text_md") return 1;
  return artifactDisplayName(left).localeCompare(artifactDisplayName(right), "ru");
}
