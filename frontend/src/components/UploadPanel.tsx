import { CheckCircle2, FileAudio, Play, Sparkles, Upload } from "lucide-react";
import { useState } from "react";
import type { DragEvent, FormEvent } from "react";

export const UPLOAD_UNSUPPORTED_MEDIA_MESSAGE =
  "Этот тип файла не поддерживается. Выберите аудио или видео файл.";

const SUPPORTED_MEDIA_EXTENSIONS = new Set([
  "mp3",
  "wav",
  "m4a",
  "aac",
  "flac",
  "ogg",
  "mp4",
  "mov",
  "mkv",
  "avi",
  "webm"
]);

const SUPPORTED_MEDIA_ACCEPT = [
  "audio/*",
  "video/*",
  ...Array.from(SUPPORTED_MEDIA_EXTENSIONS, (extension) => `.${extension}`)
].join(",");

export function isSupportedMediaFile(file: Pick<File, "name" | "type">): boolean {
  if (file.type.startsWith("audio/") || file.type.startsWith("video/")) return true;

  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  return SUPPORTED_MEDIA_EXTENSIONS.has(extension);
}

interface UploadPanelProps {
  canSubmitJob: boolean;
  isSubmitting: boolean;
  mediaFile: File | null;
  selectedModelIsReady: boolean;
  selectedModelStatusText: string;
  selectedModelTitle: string;
  speakerHint: string;
  titleError: string | null;
  transcriptionTitle: string;
  onMediaFileChange: (file: File | null) => void;
  onSpeakerHintChange: (value: string) => void;
  onSubmitJob: (event: FormEvent) => void;
  onTranscriptionTitleChange: (value: string) => void;
}

export function UploadPanel({
  canSubmitJob,
  isSubmitting,
  mediaFile,
  selectedModelIsReady,
  selectedModelStatusText,
  selectedModelTitle,
  speakerHint,
  titleError,
  transcriptionTitle,
  onMediaFileChange,
  onSpeakerHintChange,
  onSubmitJob,
  onTranscriptionTitleChange
}: UploadPanelProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileLabel = mediaFile ? mediaFile.name : "Перетащите запись сюда";
  const fileHelp = mediaFile
    ? "Файл выбран, можно уточнить название и участников."
    : "Аудио или видео: mp3, wav, m4a, mp4, mov и другие.";

  function selectMediaFile(file: File | null) {
    if (file && !isSupportedMediaFile(file)) {
      setUploadError(UPLOAD_UNSUPPORTED_MEDIA_MESSAGE);
      return;
    }

    setUploadError(null);
    onMediaFileChange(file);
  }

  function handleDrag(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "copy";
  }

  function handleDragEnter(event: DragEvent<HTMLLabelElement>) {
    handleDrag(event);
    setIsDragActive(true);
  }

  function handleDragLeave(event: DragEvent<HTMLLabelElement>) {
    handleDrag(event);
    const nextTarget = event.relatedTarget instanceof Node ? event.relatedTarget : null;
    if (!nextTarget || !event.currentTarget.contains(nextTarget)) {
      setIsDragActive(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    handleDrag(event);
    setIsDragActive(false);

    const file = event.dataTransfer.files.item(0);
    if (!file || !isSupportedMediaFile(file)) {
      setUploadError(UPLOAD_UNSUPPORTED_MEDIA_MESSAGE);
      return;
    }

    setUploadError(null);
    onMediaFileChange(file);
  }

  return (
    <form className="upload-hero" onSubmit={onSubmitJob}>
      <div className="upload-copy">
        <p className="eyebrow accent">Новая запись</p>
        <h2>Превратить запись в готовый текст</h2>
        <p>Один главный шаг: добавьте файл, проверьте название и запустите транскрибацию.</p>
        <div className="flow-steps" aria-label="Порядок работы">
          <span className={mediaFile ? "complete" : "active"}>1. Файл</span>
          <span>2. Спикеры</span>
          <span>3. Markdown</span>
        </div>
      </div>
      <label
        className={`hero-file-picker${isDragActive ? " is-drag-active" : ""}${
          uploadError ? " has-error" : ""
        }${mediaFile ? " has-file" : ""}`}
        aria-describedby={uploadError ? "upload-file-error" : undefined}
        onDragEnter={handleDragEnter}
        onDragOver={handleDrag}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <span className="upload-icon-wrap">{mediaFile ? <FileAudio size={28} /> : <Upload size={28} />}</span>
        <span>{isDragActive ? "Отпустите файл здесь" : fileLabel}</span>
        <small>{isDragActive ? "Запись сразу попадёт в форму" : fileHelp}</small>
        <input
          type="file"
          accept={SUPPORTED_MEDIA_ACCEPT}
          onChange={(event) => {
            selectMediaFile(event.target.files?.[0] ?? null);
          }}
        />
      </label>
      {uploadError && (
        <p className="upload-file-error" id="upload-file-error" role="alert">
          {uploadError}
        </p>
      )}
      <label className="speaker-input">
        <span>Название транскрибации</span>
        <input
          aria-label="Название транскрибации"
          aria-invalid={titleError ? "true" : "false"}
          aria-describedby={titleError ? "transcription-title-error" : undefined}
          required
          type="text"
          placeholder="Например: Созвон с клиентом"
          value={transcriptionTitle}
          onChange={(event) => onTranscriptionTitleChange(event.target.value)}
        />
        {titleError && (
          <span id="transcription-title-error" role="alert">
            {titleError}
          </span>
        )}
      </label>
      <label className="speaker-input">
        <span>Участники</span>
        <input
          aria-label="Кто был на встрече"
          type="text"
          placeholder="Например: Яков и Никита"
          value={speakerHint}
          onChange={(event) => onSpeakerHintChange(event.target.value)}
        />
      </label>
      <div className="upload-actions">
        <span className={`model-readiness ${selectedModelIsReady ? "ready" : "pending"}`}>
          {selectedModelIsReady ? <CheckCircle2 size={16} /> : <Sparkles size={16} />}
          <span>
            Модель: {selectedModelTitle}
            {!selectedModelIsReady && ` · ${selectedModelStatusText}`}
          </span>
        </span>
        <button className="run-button" disabled={!canSubmitJob} type="submit">
          <Play size={17} />
          <span>{isSubmitting ? "Запускаю…" : "Запустить транскрибацию"}</span>
        </button>
      </div>
    </form>
  );
}
