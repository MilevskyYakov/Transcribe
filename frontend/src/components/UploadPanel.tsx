import { FileAudio, FolderOpen, Play, Upload, X } from "lucide-react";
import { useState } from "react";
import type { DragEvent, FormEvent } from "react";

export const UPLOAD_UNSUPPORTED_MEDIA_MESSAGE =
  "Этот тип файла не поддерживается. Выберите аудио или видео файл.";

const SUPPORTED_MEDIA_EXTENSIONS = new Set([
  "mp3", "wav", "m4a", "aac", "flac", "ogg", "mp4", "mov", "mkv", "avi", "webm"
]);

const SUPPORTED_MEDIA_ACCEPT = [
  "audio/*",
  "video/*",
  ...Array.from(SUPPORTED_MEDIA_EXTENSIONS, (extension) => `.${extension}`)
].join(",");

export function isSupportedMediaFile(file: Pick<File, "name" | "type">): boolean {
  if (file.type.startsWith("audio/") || file.type.startsWith("video/")) return true;
  return SUPPORTED_MEDIA_EXTENSIONS.has(file.name.split(".").pop()?.toLowerCase() ?? "");
}

interface UploadPanelProps {
  autosaveMarkdownDir: string | null;
  canSubmitJob: boolean;
  isSubmitting: boolean;
  mediaFile: File | null;
  selectedModelIsReady: boolean;
  selectedModelStatusText: string;
  selectedModelTitle: string;
  onMediaFileChange: (file: File | null) => void;
  onOpenSettings: () => void;
  onSubmitJob: (event: FormEvent) => void;
}

export function UploadPanel({
  autosaveMarkdownDir,
  canSubmitJob,
  isSubmitting,
  mediaFile,
  selectedModelIsReady,
  selectedModelStatusText,
  selectedModelTitle,
  onMediaFileChange,
  onOpenSettings,
  onSubmitJob
}: UploadPanelProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  function handleDragLeave(event: DragEvent<HTMLLabelElement>) {
    handleDrag(event);
    const nextTarget = event.relatedTarget instanceof Node ? event.relatedTarget : null;
    if (!nextTarget || !event.currentTarget.contains(nextTarget)) setIsDragActive(false);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    handleDrag(event);
    setIsDragActive(false);
    selectMediaFile(event.dataTransfer.files.item(0));
  }

  return (
    <form className={`new-transcription-screen${mediaFile ? " has-file" : ""}`} onSubmit={onSubmitJob}>
      <header className="screen-header">
        <div>
          <p className="eyebrow">Mnema</p>
          <h1>Новая транскрипция</h1>
          <p>Добавьте аудио или видео</p>
        </div>
      </header>

      <label
        className={`drop-surface${isDragActive ? " is-drag-active" : ""}${uploadError ? " has-error" : ""}${mediaFile ? " has-file" : ""}`}
        onDragEnter={(event) => { handleDrag(event); setIsDragActive(true); }}
        onDragOver={handleDrag}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <span className="editorial-cut" aria-hidden="true" />
        {mediaFile ? <FileAudio className="drop-icon" size={34} /> : <Upload className="drop-icon" size={34} />}
        <strong>{isDragActive ? "Отпустите файлы здесь" : mediaFile?.name ?? "Перетащите записи сюда"}</strong>
        <small>{mediaFile ? "Файл готов к обработке" : "Можно добавить один или несколько файлов"}</small>
        {!mediaFile && <span className="secondary-button file-button">Выбрать файлы</span>}
        <input
          aria-label="Выбрать файл"
          type="file"
          accept={SUPPORTED_MEDIA_ACCEPT}
          onChange={(event) => selectMediaFile(event.target.files?.[0] ?? null)}
        />
      </label>

      {uploadError && <p className="inline-error" role="alert">{uploadError}</p>}

      {mediaFile && (
        <section className="file-setup">
          <button className="remove-file" aria-label="Убрать файл" type="button" onClick={() => selectMediaFile(null)}><X size={16} /> Убрать</button>
          <div className="destination-row">
            <FolderOpen size={18} />
            <span><small>Сохранить в</small><strong>{autosaveMarkdownDir ?? "Папка не выбрана"}</strong></span>
            <button className="text-button" type="button" onClick={onOpenSettings}>{autosaveMarkdownDir ? "Изменить в настройках" : "Выбрать папку"}</button>
          </div>
          {!selectedModelIsReady && (
            <div className="model-problem" role="status">
              <strong>Модель распознавания не готова</strong>
              <span>{selectedModelTitle} · {selectedModelStatusText}</span>
              <button className="text-button" type="button" onClick={onOpenSettings}>Открыть настройки моделей</button>
            </div>
          )}
          <div className="setup-actions">
            <span className="model-caption">Модель: {selectedModelTitle}</span>
            <button className="primary-button" disabled={!canSubmitJob || !autosaveMarkdownDir} type="submit">
              <Play size={17} /> {isSubmitting ? "Запускаю…" : "Начать транскрибацию"}
            </button>
          </div>
        </section>
      )}
    </form>
  );
}